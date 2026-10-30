"""
Ticket Detail page — full view of a single ticket: metadata, ML predictions,
lifecycle actions (resolve/close/reopen), and the comment thread.

The ticket ID is not a URL path param (Streamlit multipage apps don't support
those natively) — it is passed via st.session_state["selected_ticket_id"],
set by the "View Detail" button on pages/2_Tickets.py.

Lifecycle button visibility mirrors backend/services/ticket_service.py RBAC
exactly, so the UI never offers an action the API would reject:
  - Resolve : engineer/admin only, from IN_PROGRESS or REOPENED
  - Close   : engineer/admin only, from RESOLVED
  - Reopen  : reporter (own ticket) or engineer/admin, from CLOSED or RESOLVED

Assignment: engineers/admins can (re)assign a ticket to any active engineer,
via the picker populated by GET /users?role=engineer (added in Step 8.1 —
this page previously had no way to list engineer IDs, so this was deferred).
The backend places no status restriction on assign(), so neither does this
picker; it's simply gated to staff roles, matching TicketService exactly.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from frontend import api_client
from frontend.components.auth import get_role, get_user, logout, require_login

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Ticket Detail | Helpdesk AI", page_icon="🔍", layout="wide")

# ── Auth gate ─────────────────────────────────────────────────────────────────
token = require_login()
user = get_user()
role = get_role()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 👤 {user.get('full_name', 'User')}")
    st.markdown(f"**Role:** {role.title()}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()

# ── Require a selected ticket ─────────────────────────────────────────────────
# If someone lands here directly (refresh, bookmark) without going through
# the Tickets list, there is no ID to look up — send them back gracefully.
ticket_id = st.session_state.get("selected_ticket_id")
if ticket_id is None:
    st.warning("No ticket selected.")
    if st.button("← Back to Tickets"):
        st.switch_page("pages/2_Tickets.py")
    st.stop()

# ── Fetch ticket ───────────────────────────────────────────────────────────────
try:
    ticket = api_client.get_ticket(token, ticket_id)
except ValueError as e:
    # Covers both 404 (not found) and 403 (employee viewing someone else's ticket)
    st.error(str(e))
    if st.button("← Back to Tickets"):
        st.switch_page("pages/2_Tickets.py")
    st.stop()
except Exception:
    st.error("⚠️ Could not reach the backend. Is the FastAPI server running?")
    st.stop()

# ── Badge helpers (same mapping used on the Tickets list page) ───────────────
PRIORITY_BADGE = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🟠 High",
    "critical": "🔴 Critical",
}
STATUS_BADGE = {
    "open": "🟡 Open",
    "in_progress": "🔵 In Progress",
    "resolved": "🟢 Resolved",
    "closed": "⚫ Closed",
    "reopened": "🔁 Reopened",
}

# ── Header ─────────────────────────────────────────────────────────────────────
col_back, col_title = st.columns([1, 5])
with col_back:
    if st.button("← Back"):
        st.switch_page("pages/2_Tickets.py")

st.title(f"🎫 {ticket['ticket_number']}")
st.subheader(ticket["title"])

status = ticket["status"]
priority = ticket["priority"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Status", STATUS_BADGE.get(status, status))
col2.metric("Priority", PRIORITY_BADGE.get(priority, priority))
col3.metric(
    "Department", ticket["department"]["name"] if ticket.get("department") else "Unassigned"
)
col4.metric("Assignee", ticket["assignee"]["full_name"] if ticket.get("assignee") else "Unassigned")

if ticket.get("sla_breached"):
    st.error("🚨 This ticket has breached its SLA.")

st.divider()

# ── Description ────────────────────────────────────────────────────────────────
st.markdown("#### Description")
st.write(ticket["description"])

st.caption(
    f"Reported by **{ticket['reporter']['full_name']}** on "
    f"{ticket['created_at'][:10]}  |  Last updated {ticket['updated_at'][:10]}"
)

st.divider()

# ── ML prediction panel ────────────────────────────────────────────────────────
# These fields are only populated if the ML models loaded successfully at
# ticket-creation time (see ml/service.py — degrades gracefully to None).
score = ticket.get("predicted_priority_score")
sla_prob = ticket.get("predicted_sla_breach_prob")
res_hours = ticket.get("predicted_resolution_hours")

if score is not None or sla_prob is not None or res_hours is not None:
    st.markdown("#### 🤖 AI Predictions")
    p1, p2, p3 = st.columns(3)
    p1.metric("Priority Score", f"{float(score) * 100:.0f}%" if score is not None else "—")
    p2.metric("SLA Breach Risk", f"{float(sla_prob) * 100:.0f}%" if sla_prob is not None else "—")
    p3.metric("Est. Resolution", f"{float(res_hours):.1f} hrs" if res_hours is not None else "—")
    st.divider()

is_staff = role in ("engineer", "admin")
is_reporter = ticket["reporter"]["id"] == user.get("id")

# ── Assignment ──────────────────────────────────────────────────────────────
# Staff can (re)assign to any active engineer. No status gate here because
# TicketService.assign_ticket() itself has none — it's valid at any point
# in the lifecycle (e.g. reassigning a ticket that's already in progress).
if is_staff:
    st.markdown("#### Assign")
    try:
        engineers_result = api_client.list_users(
            token, role="engineer", is_active=True, page_size=100
        )
        engineers = engineers_result.get("items", [])
    except ValueError as e:
        engineers = []
        st.error(f"Could not load engineers: {e}")

    if not engineers:
        st.caption("No active engineers available to assign.")
    else:
        current_assignee_id = ticket["assignee"]["id"] if ticket.get("assignee") else None
        engineer_ids = [e["id"] for e in engineers]
        default_index = (
            engineer_ids.index(current_assignee_id) if current_assignee_id in engineer_ids else 0
        )

        col_pick, col_go = st.columns([3, 1])
        with col_pick:
            chosen_id = st.selectbox(
                "Engineer",
                options=engineer_ids,
                index=default_index,
                format_func=lambda uid: next(e["full_name"] for e in engineers if e["id"] == uid),
                label_visibility="collapsed",
            )
        with col_go:
            if st.button("Assign", use_container_width=True):
                try:
                    api_client.assign_ticket(token, ticket_id, chosen_id)
                    st.success("Ticket assigned.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.divider()

# ── Lifecycle actions ──────────────────────────────────────────────────────────
# Visibility mirrors backend RBAC exactly (see module docstring above) so a
# button never appears only to be rejected by the API.

can_resolve = is_staff and status in ("in_progress", "reopened")
can_close = is_staff and status == "resolved"
can_reopen = (is_staff or is_reporter) and status in ("closed", "resolved")

if can_resolve or can_close or can_reopen:
    st.markdown("#### Actions")
    action_cols = st.columns(3)

    if can_resolve:
        with action_cols[0]:
            if st.button("✅ Mark Resolved", use_container_width=True):
                try:
                    api_client.resolve_ticket(token, ticket_id)
                    st.success("Ticket marked as resolved.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    if can_close:
        with action_cols[1]:
            if st.button("⚫ Close Ticket", use_container_width=True):
                try:
                    api_client.close_ticket(token, ticket_id)
                    st.success("Ticket closed.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    if can_reopen:
        with action_cols[2]:
            if st.button("🔁 Reopen Ticket", use_container_width=True):
                try:
                    api_client.reopen_ticket(token, ticket_id)
                    st.success("Ticket reopened.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.divider()

# ── Comments ───────────────────────────────────────────────────────────────────
st.markdown("#### 💬 Comments")

try:
    comments = api_client.get_comments(token, ticket_id)
except ValueError as e:
    comments = []
    st.error(f"Could not load comments: {e}")

if not comments:
    st.caption("No comments yet.")
else:
    for c in comments:
        badge = " 🔒 Internal" if c.get("is_internal") else ""
        with st.chat_message("user"):
            st.markdown(f"**{c['author']['full_name']}**{badge}  \n{c['body']}")
            st.caption(c["created_at"][:16].replace("T", " "))

# Employees cannot post internal notes — hide the checkbox for them entirely
# rather than show it and reject the request server-side.
with st.form("add_comment_form", clear_on_submit=True):
    body = st.text_area("Add a comment", placeholder="Type an update...", height=100)
    is_internal = st.checkbox("Internal note (staff only)") if is_staff else False
    submitted = st.form_submit_button("Post Comment")

if submitted:
    if not body.strip():
        st.error("Comment cannot be empty.")
    else:
        try:
            api_client.add_comment(token, ticket_id, body.strip(), is_internal)
            st.rerun()
        except ValueError as e:
            st.error(str(e))
        except Exception:
            st.error("⚠️ Could not reach the backend.")

st.divider()

# ── Attachments ─────────────────────────────────────────────────────────────────
# Mirrors the Comments section above: list existing items, then a form to
# add a new one. Download uses st.download_button rather than a link —
# the file has to come from an authenticated API call (see api_client.
# download_attachment), not a raw static URL, so it must be fetched into
# memory first.
st.markdown("#### 📎 Attachments")

try:
    attachments = api_client.list_attachments(token, ticket_id)
except ValueError as e:
    attachments = []
    st.error(f"Could not load attachments: {e}")

if not attachments:
    st.caption("No attachments yet.")
else:
    for a in attachments:
        size_kb = a["file_size_bytes"] / 1024
        col_info, col_dl = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{a['file_name']}**  \n"
                f"{size_kb:.1f} KB · uploaded by {a['uploaded_by']['full_name']} "
                f"on {a['uploaded_at'][:10]}"
            )
        with col_dl:
            try:
                file_bytes = api_client.download_attachment(token, ticket_id, a["id"])
                st.download_button(
                    "Download",
                    data=file_bytes,
                    file_name=a["file_name"],
                    mime=a["mime_type"],
                    key=f"download_{a['id']}",
                    use_container_width=True,
                )
            except ValueError as e:
                st.error(str(e))

with st.form("add_attachment_form", clear_on_submit=True):
    uploaded_file = st.file_uploader(
        "Attach a file",
        help="Max 10 MB. Images, PDFs, text/CSV, Word, Excel, and zip files are allowed.",
    )
    upload_submitted = st.form_submit_button("Upload")

if upload_submitted:
    if uploaded_file is None:
        st.error("Choose a file first.")
    else:
        try:
            api_client.upload_attachment(
                token,
                ticket_id,
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
            st.success("Attachment uploaded.")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
        except Exception:
            st.error("⚠️ Could not reach the backend.")

st.divider()

# ── History (audit trail) ────────────────────────────────────────────────────
# Read-only, chronological. Field names shown here match TicketService's
# field_changed strings exactly (see backend/services/ticket_service.py
# _record_history call sites) — this map is purely cosmetic labeling,
# not a source of truth.
FIELD_LABELS = {
    "status": "Status",
    "priority": "Priority",
    "assigned_to_id": "Assignee (user ID)",
    "department_id": "Department (ID)",
    "title": "Title",
    "description": "Description",
}

with st.expander("🕘 History"):
    try:
        history = api_client.get_ticket_history(token, ticket_id)
    except ValueError as e:
        history = []
        st.error(f"Could not load history: {e}")

    if not history:
        st.caption("No tracked changes yet.")
    else:
        for h in history:
            label = FIELD_LABELS.get(h["field_changed"], h["field_changed"])
            old = h["old_value"] if h["old_value"] is not None else "—"
            new = h["new_value"] if h["new_value"] is not None else "—"
            st.markdown(
                f"**{label}**: {old} → {new}  \n"
                f"<span style='color:gray;font-size:0.85em'>"
                f"{h['changed_by']['full_name']} · {h['changed_at'][:16].replace('T', ' ')}"
                f"</span>",
                unsafe_allow_html=True,
            )
