"""
API client for helpdesk-ai FastAPI backend.

All HTTP communication lives here — Streamlit pages never
import 'requests' directly. This makes it easy to:
- Change the base URL (dev → staging → prod) in one place
- Add logging or retry logic centrally
- Mock in tests
"""

from __future__ import annotations  # enables "dict | list" syntax on Python 3.9

import os
from typing import Any

import requests

# =====================================================
# Configuration
# =====================================================

# Reads API_BASE_URL from the environment, falling back to localhost for
# native (non-Docker) dev — unchanged default behavior for anyone running
# `streamlit run frontend/Home.py` directly.
#
# This matters once the frontend runs in its own container: a container
# can't reach a sibling container via "localhost" (that resolves to
# itself), so docker-compose.yml overrides this to "http://backend:8000"
# via the frontend service's `environment:` block. Hardcoding localhost
# here would silently break every API call inside that container with a
# connection-refused error that has nothing to do with the actual code.
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000") + "/api/v1"

# Configurable via env var because Render's free tier spins a web service
# down after ~15 minutes idle and takes 30-60s to cold-start on the next
# request. A hardcoded 10s timeout would make the very first request after
# idle time fail with a misleading "cannot connect to backend" error, even
# though the backend is just slow to wake up, not actually down. Local/native
# dev keeps the original 10s default since there's no cold start to wait out.
TIMEOUT = int(os.environ.get("API_TIMEOUT_SECONDS", "10"))  # seconds


# =====================================================
# Internal helpers
# =====================================================


def _headers(token: str) -> dict:
    """Build Authorization header from JWT token."""
    return {"Authorization": f"Bearer {token}"}


def _handle(response: requests.Response) -> Any:
    """
    Raise a readable error on non-2xx responses.
    Returns parsed JSON on success.
    """
    try:
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise ValueError(f"[{response.status_code}] {detail}") from exc


def _handle_binary(response: requests.Response) -> bytes:
    """
    Same error handling as _handle(), but for endpoints that return a raw
    file (report exports, attachment downloads) instead of JSON. Calling
    response.json() on a PDF/xlsx/attachment body would crash, so this is
    a separate path rather than a branch inside _handle().
    """
    try:
        response.raise_for_status()
        return response.content
    except requests.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise ValueError(f"[{response.status_code}] {detail}") from exc


def _handle_no_content(response: requests.Response) -> None:
    """Like _handle(), but for 204 No Content endpoints with no JSON body."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise ValueError(f"[{response.status_code}] {detail}") from exc


# =====================================================
# Auth
# =====================================================


def login(email: str, password: str) -> dict:
    """
    POST /auth/login — returns access_token and refresh_token.
    Uses form encoding (OAuth2 requirement).
    """
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password},
        timeout=TIMEOUT,
    )
    return _handle(response)


def register(full_name: str, email: str, username: str, password: str) -> dict:
    """
    POST /auth/register — self-service registration.

    Always creates an 'employee' account; the backend hardcodes that role
    server-side regardless of what's sent here (see AuthService.register()),
    so there is no role field to pass. Creating engineer/admin accounts
    goes through create_user() below instead, which is admin-only.
    """
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "full_name": full_name,
            "email": email,
            "username": username,
            "password": password,
        },
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_current_user(token: str) -> dict:
    """GET /auth/me — returns current user profile."""
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def forgot_password(email: str) -> dict:
    """
    POST /auth/forgot-password — always returns 202 with a generic message,
    regardless of whether the email is registered (see backend docstring).
    """
    response = requests.post(
        f"{BASE_URL}/auth/forgot-password",
        json={"email": email},
        timeout=TIMEOUT,
    )
    return _handle(response)


def reset_password(token: str, new_password: str) -> None:
    """POST /auth/reset-password — redeems a reset token for a new password."""
    response = requests.post(
        f"{BASE_URL}/auth/reset-password",
        json={"token": token, "new_password": new_password},
        timeout=TIMEOUT,
    )
    _handle_no_content(response)


# =====================================================
# Tickets
# =====================================================


def list_tickets(
    token: str,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    priority: str | None = None,
) -> dict:
    """GET /tickets — paginated list with optional filters."""
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority

    response = requests.get(
        f"{BASE_URL}/tickets",
        headers=_headers(token),
        params=params,
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_ticket(token: str, ticket_id: int) -> dict:
    """GET /tickets/{ticket_id} — single ticket detail."""
    response = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def create_ticket(token: str, payload: dict) -> dict:
    """POST /tickets — create a new ticket."""
    response = requests.post(
        f"{BASE_URL}/tickets",
        headers=_headers(token),
        json=payload,
        timeout=TIMEOUT,
    )
    return _handle(response)


def assign_ticket(token: str, ticket_id: int, assignee_id: int) -> dict:
    """POST /tickets/{ticket_id}/assign."""
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/assign",
        headers=_headers(token),
        json={"assignee_id": assignee_id},
        timeout=TIMEOUT,
    )
    return _handle(response)


def resolve_ticket(token: str, ticket_id: int) -> dict:
    """POST /tickets/{ticket_id}/resolve."""
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/resolve",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def close_ticket(token: str, ticket_id: int) -> dict:
    """POST /tickets/{ticket_id}/close."""
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/close",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def reopen_ticket(token: str, ticket_id: int) -> dict:
    """POST /tickets/{ticket_id}/reopen."""
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/reopen",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def add_comment(token: str, ticket_id: int, body: str, is_internal: bool = False) -> dict:
    """POST /tickets/{ticket_id}/comments."""
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/comments",
        headers=_headers(token),
        json={"body": body, "is_internal": is_internal},
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_comments(token: str, ticket_id: int) -> list:
    """GET /tickets/{ticket_id}/comments."""
    response = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}/comments",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_ticket_history(token: str, ticket_id: int) -> list:
    """GET /tickets/{ticket_id}/history — chronological audit trail."""
    response = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}/history",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


# =====================================================
# Attachments
# =====================================================


def upload_attachment(
    token: str, ticket_id: int, filename: str, content: bytes, content_type: str
) -> dict:
    """
    POST /tickets/{ticket_id}/attachments — multipart upload.

    Deliberately does NOT set a "Content-Type": "application/json" header
    (unlike every other write in this module) — `files=` tells requests to
    build a multipart/form-data body and set its own boundary-aware
    Content-Type. Passing json= here would silently send the wrong body.
    """
    response = requests.post(
        f"{BASE_URL}/tickets/{ticket_id}/attachments",
        headers=_headers(token),
        files={"file": (filename, content, content_type)},
        timeout=TIMEOUT,
    )
    return _handle(response)


def list_attachments(token: str, ticket_id: int) -> list:
    """GET /tickets/{ticket_id}/attachments."""
    response = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}/attachments",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def download_attachment(token: str, ticket_id: int, attachment_id: int) -> bytes:
    """GET /tickets/{ticket_id}/attachments/{attachment_id}/download — raw file bytes."""
    response = requests.get(
        f"{BASE_URL}/tickets/{ticket_id}/attachments/{attachment_id}/download",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle_binary(response)


# =====================================================
# Dashboard
# =====================================================


def get_dashboard_summary(token: str) -> dict:
    """GET /dashboard/summary."""
    response = requests.get(
        f"{BASE_URL}/dashboard/summary",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_dashboard_trends(token: str) -> list:
    """GET /dashboard/trends."""
    response = requests.get(
        f"{BASE_URL}/dashboard/trends",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_sla_stats(token: str) -> list:
    """GET /dashboard/sla."""
    response = requests.get(
        f"{BASE_URL}/dashboard/sla",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_engineer_stats(token: str) -> list:
    """GET /dashboard/engineers."""
    response = requests.get(
        f"{BASE_URL}/dashboard/engineers",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def get_heatmap_data(token: str) -> list:
    """GET /dashboard/heatmap — ticket counts by day-of-week x hour."""
    response = requests.get(
        f"{BASE_URL}/dashboard/heatmap",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


# =====================================================
# Users
# =====================================================


def list_users(
    token: str,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
) -> dict:
    """GET /users — paginated, filterable roster. Engineer/admin only."""
    params: dict[str, Any] = {"page": page, "page_size": page_size}
    if role:
        params["role"] = role
    if department_id:
        params["department_id"] = department_id
    if is_active is not None:
        params["is_active"] = is_active

    response = requests.get(
        f"{BASE_URL}/users",
        headers=_headers(token),
        params=params,
        timeout=TIMEOUT,
    )
    return _handle(response)


def create_user(
    token: str,
    full_name: str,
    email: str,
    username: str,
    password: str,
    role: str,
    department_id: int | None = None,
) -> dict:
    """
    POST /users — admin-only user creation with an explicit role.

    Unlike register() above, this can create engineer/admin accounts —
    that's exactly why it requires an admin's token and hits a separate,
    admin-gated endpoint rather than reusing /auth/register.
    """
    payload: dict[str, Any] = {
        "full_name": full_name,
        "email": email,
        "username": username,
        "password": password,
        "role": role,
    }
    if department_id is not None:
        payload["department_id"] = department_id

    response = requests.post(
        f"{BASE_URL}/users",
        headers=_headers(token),
        json=payload,
        timeout=TIMEOUT,
    )
    return _handle(response)


def deactivate_user(token: str, user_id: int) -> dict:
    """POST /users/{user_id}/deactivate. Admin only."""
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/deactivate",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def activate_user(token: str, user_id: int) -> dict:
    """POST /users/{user_id}/activate. Admin only."""
    response = requests.post(
        f"{BASE_URL}/users/{user_id}/activate",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


# =====================================================
# Departments
# =====================================================


def list_departments(token: str) -> list:
    """GET /departments — used to populate the department picker on the admin Add User form."""
    response = requests.get(
        f"{BASE_URL}/departments",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


# =====================================================
# SLA Policies
# =====================================================


def get_sla_policies(token: str) -> list:
    """GET /sla-policies. Engineer/admin only."""
    response = requests.get(
        f"{BASE_URL}/sla-policies",
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    return _handle(response)


def update_sla_policy(token: str, policy_id: int, payload: dict) -> dict:
    """PATCH /sla-policies/{policy_id}. Admin only."""
    response = requests.patch(
        f"{BASE_URL}/sla-policies/{policy_id}",
        headers=_headers(token),
        json=payload,
        timeout=TIMEOUT,
    )
    return _handle(response)


# =====================================================
# Reports
# =====================================================

_REPORT_ENDPOINTS = {
    "csv": "csv",
    "excel": "excel",
    "pdf": "pdf",
}


def export_tickets_report(
    token: str,
    fmt: str,
    status: str | None = None,
    priority: str | None = None,
    department_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bytes:
    """
    GET /reports/tickets/{csv,excel,pdf} — returns raw file bytes.

    fmt must be one of "csv", "excel", "pdf". date_from/date_to are
    ISO date strings ("YYYY-MM-DD") — Streamlit's st.date_input gives
    a date object, so callers should str() it first.
    """
    if fmt not in _REPORT_ENDPOINTS:
        raise ValueError(
            f"Unknown report format: {fmt!r}. Expected one of {list(_REPORT_ENDPOINTS)}."
        )

    params: dict[str, Any] = {}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    if department_id:
        params["department_id"] = department_id
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    response = requests.get(
        f"{BASE_URL}/reports/tickets/{_REPORT_ENDPOINTS[fmt]}",
        headers=_headers(token),
        params=params,
        timeout=TIMEOUT,
    )
    return _handle_binary(response)
