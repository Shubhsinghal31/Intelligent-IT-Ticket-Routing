"""
Forgot Password / Reset Password integration tests.

Exercises the real chain: HTTP request -> AuthService -> PasswordResetToken
(hashed, single-use) -> real Postgres -> HTTP request again to redeem it.

Email delivery itself (backend/core/email.send_email) is patched in these
tests — not because it's untrustworthy, but because there's no mailbox to
read from in a test run, and the raw reset token only ever exists in the
email body (only its SHA-256 hash is persisted, by design — see
PasswordResetToken's docstring). Patching send_email is the seam that lets
the test capture the raw token exactly as a real user would receive it,
while every other part of the request — routing, rate limiting, the
service, the database — runs unmodified.
"""

import re
from unittest.mock import patch

from tests.integration.conftest import TEST_PASSWORD, register


def _request_reset_and_capture_token(client, email: str) -> str:
    """
    POST /auth/forgot-password with send_email patched, and return the raw
    token pulled out of the "sent" email body's reset link.
    """
    captured = {}

    def fake_send_email(to, subject, body):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body

    with patch("backend.services.auth_service.send_email", side_effect=fake_send_email):
        response = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert response.status_code == 202, response.text

    match = re.search(r"reset_token=(\S+)", captured["body"])
    assert match, f"No reset_token found in emailed body: {captured['body']!r}"
    assert captured["to"] == email
    return match.group(1)


class TestForgotPassword:
    def test_returns_202_for_registered_email(self, client):
        register(client, "forgot.known@example.com", "forgot_known", "Forgot Known")

        response = client.post(
            "/api/v1/auth/forgot-password", json={"email": "forgot.known@example.com"}
        )

        assert response.status_code == 202
        assert "message" in response.json()

    def test_returns_202_for_unregistered_email_too(self, client):
        """
        Same status and message whether or not the email exists — this is
        the user-enumeration defense described in AuthService.request_
        password_reset's docstring. A different response here (404 vs 202,
        or a different message) would let an attacker discover which
        emails have accounts just by probing this endpoint.
        """
        response = client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody.registered@example.com"}
        )

        assert response.status_code == 202
        assert "message" in response.json()

    def test_is_rate_limited(self, client):
        """RATE_LIMIT_FORGOT_PASSWORD is 3/minute — the 4th request in a row should 429."""
        for _ in range(3):
            response = client.post(
                "/api/v1/auth/forgot-password", json={"email": "rate.limited@example.com"}
            )
            assert response.status_code == 202

        fourth = client.post(
            "/api/v1/auth/forgot-password", json={"email": "rate.limited@example.com"}
        )
        assert fourth.status_code == 429


class TestResetPassword:
    def test_full_flow_old_password_stops_working_new_one_does(self, client):
        register(client, "reset.flow@example.com", "reset_flow", "Reset Flow")
        raw_token = _request_reset_and_capture_token(client, "reset.flow@example.com")

        reset_response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "BrandNewPass123!"},
        )
        assert reset_response.status_code == 204

        old_password_login = client.post(
            "/api/v1/auth/login",
            data={"username": "reset.flow@example.com", "password": TEST_PASSWORD},
        )
        assert old_password_login.status_code == 401

        new_password_login = client.post(
            "/api/v1/auth/login",
            data={"username": "reset.flow@example.com", "password": "BrandNewPass123!"},
        )
        assert new_password_login.status_code == 200

    def test_token_is_single_use(self, client):
        register(client, "reset.reuse@example.com", "reset_reuse", "Reset Reuse")
        raw_token = _request_reset_and_capture_token(client, "reset.reuse@example.com")

        first_attempt = client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "FirstNewPass123!"},
        )
        assert first_attempt.status_code == 204

        second_attempt = client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "SecondNewPass123!"},
        )
        assert second_attempt.status_code == 401

    def test_garbage_token_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-real-token", "new_password": "SomeNewPass123!"},
        )
        assert response.status_code == 401

    def test_weak_new_password_returns_422(self, client):
        register(client, "reset.weak@example.com", "reset_weak", "Reset Weak")
        raw_token = _request_reset_and_capture_token(client, "reset.weak@example.com")

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "weak"},
        )
        assert response.status_code == 422
