"""
Unit tests for AuthService business logic.

These mock UserRepository and the DB session, so they run without a
database connection. Password hashing and JWT encode/decode are pure
functions with no DB dependency — real bcrypt/JWT calls are used where
it's cheap (JWT) and mocked where it isn't (bcrypt is intentionally
slow, ~100ms per call at cost factor 12; mocking it keeps this file
fast without weakening what it actually verifies, which is AuthService's
branching logic, not bcrypt itself).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.exceptions import ConflictException, NotFoundException, UnauthorizedException
from backend.core.security import create_access_token, create_refresh_token, decode_token
from backend.schemas.user import UserRegister
from backend.services.auth_service import AuthService

# =====================================================
# Helpers
# =====================================================


def make_service():
    """Return an AuthService with a mocked DB session and repositories."""
    db = MagicMock()
    service = AuthService(db)
    service.user_repo = MagicMock()
    service.reset_token_repo = MagicMock()
    return service


def make_register_payload(**overrides) -> UserRegister:
    defaults = {
        "email": "new.hire@example.com",
        "username": "new_hire",
        "password": "SecurePass123!",
        "full_name": "New Hire",
    }
    defaults.update(overrides)
    return UserRegister(**defaults)


# =====================================================
# register()
# =====================================================


class TestRegister:
    def test_creates_user_with_employee_role(self, employee_role):
        employee_role.id = 3
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = employee_role

        with patch("backend.services.auth_service.hash_password", return_value="hashed-value"):
            user = service.register(make_register_payload())

        assert user.email == "new.hire@example.com"
        assert user.username == "new_hire"
        assert user.password_hash == "hashed-value"
        assert user.role_id == 3
        assert user.department_id is None
        assert user.is_active is True
        service.user_repo.get_role_by_name.assert_called_once_with("employee")
        service.user_repo.add.assert_called_once()
        service.user_repo.commit.assert_called_once()

    def test_lowercases_email(self, employee_role):
        """
        Note: UserRegister.username already enforces a lowercase-only
        pattern at the Pydantic layer (^[a-z0-9_]+$), so a mixed-case
        username can never reach the service. Email has no such
        constraint (EmailStr allows mixed case), so the service's own
        .lower() call is what's actually being tested here.
        """
        employee_role.id = 3
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = employee_role

        with patch("backend.services.auth_service.hash_password", return_value="x"):
            user = service.register(make_register_payload(email="Mixed.Case@Example.com"))

        assert user.email == "mixed.case@example.com"

    def test_duplicate_email_raises_conflict(self):
        service = make_service()
        service.user_repo.email_exists.return_value = True

        with pytest.raises(ConflictException):
            service.register(make_register_payload())

        # Should short-circuit before ever checking username or role
        service.user_repo.username_exists.assert_not_called()
        service.user_repo.add.assert_not_called()

    def test_duplicate_username_raises_conflict(self):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = True

        with pytest.raises(ConflictException):
            service.register(make_register_payload())

        service.user_repo.add.assert_not_called()

    def test_missing_employee_role_raises_not_found(self):
        service = make_service()
        service.user_repo.email_exists.return_value = False
        service.user_repo.username_exists.return_value = False
        service.user_repo.get_role_by_name.return_value = None

        with pytest.raises(NotFoundException):
            service.register(make_register_payload())

        service.user_repo.add.assert_not_called()


# =====================================================
# authenticate()
# =====================================================


class TestAuthenticate:
    def test_unknown_email_raises_unauthorized(self):
        service = make_service()
        service.user_repo.get_by_email.return_value = None

        with patch("backend.services.auth_service.verify_password") as mock_verify:
            with pytest.raises(UnauthorizedException):
                service.authenticate("nobody@example.com", "whatever")

        # Constant-time defense: still runs a dummy bcrypt verify even
        # though there's no real user to compare against.
        mock_verify.assert_called_once()

    def test_wrong_password_raises_unauthorized(self, employee_user):
        employee_user.password_hash = "stored-hash"
        service = make_service()
        service.user_repo.get_by_email.return_value = employee_user

        with patch("backend.services.auth_service.verify_password", return_value=False):
            with pytest.raises(UnauthorizedException):
                service.authenticate("alice@example.com", "wrong-password")

        service.user_repo.update_last_login.assert_not_called()

    def test_inactive_user_raises_unauthorized(self, employee_user):
        employee_user.is_active = False
        service = make_service()
        service.user_repo.get_by_email.return_value = employee_user

        with patch("backend.services.auth_service.verify_password", return_value=True):
            with pytest.raises(UnauthorizedException):
                service.authenticate("alice@example.com", "correct-password")

    def test_successful_login_updates_last_login_and_returns_user(self, employee_user):
        employee_user.is_active = True
        service = make_service()
        service.user_repo.get_by_email.return_value = employee_user

        with patch("backend.services.auth_service.verify_password", return_value=True):
            result = service.authenticate("alice@example.com", "correct-password")

        assert result is employee_user
        service.user_repo.update_last_login.assert_called_once_with(employee_user)
        service.user_repo.commit.assert_called_once()


# =====================================================
# issue_tokens()
# =====================================================


class TestIssueTokens:
    def test_returns_tokens_with_expected_claims(self, employee_user):
        employee_user.id = 42
        employee_user.username = "alice"
        service = make_service()

        tokens = service.issue_tokens(employee_user)

        access_payload = decode_token(tokens.access_token, expected_type="access")
        refresh_payload = decode_token(tokens.refresh_token, expected_type="refresh")

        assert access_payload["sub"] == "42"
        assert access_payload["role"] == "employee"
        assert access_payload["username"] == "alice"
        assert refresh_payload["sub"] == "42"
        assert tokens.expires_in > 0


# =====================================================
# refresh_access_token()
# =====================================================


class TestRefreshAccessToken:
    def test_valid_refresh_token_issues_new_access_token(self, employee_user):
        employee_user.id = 42
        service = make_service()
        service.user_repo.get_by_id.return_value = employee_user
        refresh_token = create_refresh_token(employee_user.id)

        result = service.refresh_access_token(refresh_token)

        access_payload = decode_token(result.access_token, expected_type="access")
        assert access_payload["sub"] == "42"

    def test_garbage_token_raises_unauthorized(self):
        service = make_service()

        with pytest.raises(UnauthorizedException):
            service.refresh_access_token("not-a-real-jwt")

    def test_access_token_used_as_refresh_is_rejected(self, employee_user):
        """
        A caller passing an access token where a refresh token is expected
        should be rejected — decode_token's expected_type check exists
        specifically to prevent access tokens (shorter-lived, narrower
        intent) from being reused as refresh tokens.
        """
        service = make_service()
        access_token = create_access_token(employee_user.id)

        with pytest.raises(UnauthorizedException):
            service.refresh_access_token(access_token)

    def test_inactive_user_raises_unauthorized(self, employee_user):
        employee_user.is_active = False
        service = make_service()
        service.user_repo.get_by_id.return_value = employee_user
        refresh_token = create_refresh_token(employee_user.id)

        with pytest.raises(UnauthorizedException):
            service.refresh_access_token(refresh_token)

    def test_deleted_user_raises_unauthorized(self, employee_user):
        service = make_service()
        service.user_repo.get_by_id.return_value = None
        refresh_token = create_refresh_token(employee_user.id)

        with pytest.raises(UnauthorizedException):
            service.refresh_access_token(refresh_token)


# =====================================================
# change_password()
# =====================================================


class TestChangePassword:
    def test_wrong_current_password_raises_unauthorized(self, employee_user):
        service = make_service()

        with patch("backend.services.auth_service.verify_password", return_value=False):
            with pytest.raises(UnauthorizedException):
                service.change_password(employee_user, "wrong-current", "NewSecurePass123!")

        service.user_repo.commit.assert_not_called()

    def test_success_updates_hash_and_commits(self, employee_user):
        employee_user.password_hash = "old-hash"
        service = make_service()

        with (
            patch("backend.services.auth_service.verify_password", return_value=True),
            patch("backend.services.auth_service.hash_password", return_value="new-hash"),
        ):
            service.change_password(employee_user, "correct-current", "NewSecurePass123!")

        assert employee_user.password_hash == "new-hash"
        service.user_repo.commit.assert_called_once()


# =====================================================
# get_user_from_token()
# =====================================================


class TestGetUserFromToken:
    def test_valid_token_returns_user(self, employee_user):
        employee_user.id = 42
        employee_user.is_active = True
        service = make_service()
        service.user_repo.get_by_id.return_value = employee_user
        token = create_access_token(employee_user.id)

        result = service.get_user_from_token(token)

        assert result is employee_user

    def test_garbage_token_raises_unauthorized(self):
        service = make_service()

        with pytest.raises(UnauthorizedException):
            service.get_user_from_token("not-a-real-jwt")

    def test_unknown_user_raises_unauthorized(self):
        service = make_service()
        service.user_repo.get_by_id.return_value = None
        token = create_access_token(999)

        with pytest.raises(UnauthorizedException):
            service.get_user_from_token(token)

    def test_inactive_user_raises_unauthorized(self, employee_user):
        employee_user.is_active = False
        service = make_service()
        service.user_repo.get_by_id.return_value = employee_user
        token = create_access_token(employee_user.id)

        with pytest.raises(UnauthorizedException):
            service.get_user_from_token(token)


# =====================================================
# request_password_reset()
# =====================================================


class TestRequestPasswordReset:
    def test_unknown_email_does_not_create_token_or_send_email(self):
        service = make_service()
        service.user_repo.get_by_email.return_value = None

        with patch("backend.services.auth_service.send_email") as mock_send:
            result = service.request_password_reset("nobody@example.com")

        assert result is None
        service.reset_token_repo.add.assert_not_called()
        mock_send.assert_not_called()

    def test_inactive_user_does_not_create_token_or_send_email(self, employee_user):
        employee_user.is_active = False
        service = make_service()
        service.user_repo.get_by_email.return_value = employee_user

        with patch("backend.services.auth_service.send_email") as mock_send:
            service.request_password_reset("alice@example.com")

        service.reset_token_repo.add.assert_not_called()
        mock_send.assert_not_called()

    def test_active_user_creates_hashed_token_and_emails_link(self, employee_user):
        import hashlib

        employee_user.id = 10
        employee_user.email = "alice@example.com"
        employee_user.full_name = "Alice Example"
        employee_user.is_active = True
        service = make_service()
        service.user_repo.get_by_email.return_value = employee_user

        with (
            patch(
                "backend.services.auth_service.secrets.token_urlsafe",
                return_value="fixed-raw-token",
            ),
            patch("backend.services.auth_service.send_email") as mock_send,
        ):
            service.request_password_reset("alice@example.com")

        # The stored token must be a hash, never the raw value.
        service.reset_token_repo.add.assert_called_once()
        created_token = service.reset_token_repo.add.call_args[0][0]
        assert created_token.user_id == 10
        assert created_token.token_hash == hashlib.sha256(b"fixed-raw-token").hexdigest()
        service.reset_token_repo.commit.assert_called_once()

        # The raw (unhashed) token is what actually goes out in the email.
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["to"] == "alice@example.com"
        assert "fixed-raw-token" in kwargs["body"]


# =====================================================
# reset_password()
# =====================================================


class TestResetPassword:
    def test_unknown_token_raises_unauthorized(self):
        service = make_service()
        service.reset_token_repo.get_by_token_hash.return_value = None

        with pytest.raises(UnauthorizedException):
            service.reset_password("garbage-token", "NewSecurePass123!")

    def test_expired_or_used_token_raises_unauthorized(self):
        service = make_service()
        stale_token = MagicMock(is_valid=False)
        service.reset_token_repo.get_by_token_hash.return_value = stale_token

        with pytest.raises(UnauthorizedException):
            service.reset_password("stale-token", "NewSecurePass123!")

        service.reset_token_repo.commit.assert_not_called()

    def test_deleted_user_raises_unauthorized(self):
        service = make_service()
        valid_token = MagicMock(is_valid=True, user_id=999)
        service.reset_token_repo.get_by_token_hash.return_value = valid_token
        service.user_repo.get_by_id.return_value = None

        with pytest.raises(UnauthorizedException):
            service.reset_password("valid-token", "NewSecurePass123!")

    def test_inactive_user_raises_unauthorized(self, employee_user):
        employee_user.is_active = False
        service = make_service()
        valid_token = MagicMock(is_valid=True, user_id=employee_user.id)
        service.reset_token_repo.get_by_token_hash.return_value = valid_token
        service.user_repo.get_by_id.return_value = employee_user

        with pytest.raises(UnauthorizedException):
            service.reset_password("valid-token", "NewSecurePass123!")

    def test_valid_token_updates_password_and_marks_token_used(self, employee_user):
        employee_user.is_active = True
        service = make_service()
        valid_token = MagicMock(is_valid=True, user_id=employee_user.id, used_at=None)
        service.reset_token_repo.get_by_token_hash.return_value = valid_token
        service.user_repo.get_by_id.return_value = employee_user

        with patch("backend.services.auth_service.hash_password", return_value="new-hash"):
            service.reset_password("valid-token", "NewSecurePass123!")

        assert employee_user.password_hash == "new-hash"
        assert valid_token.used_at is not None
        service.reset_token_repo.commit.assert_called_once()
