"""
Password complexity validator.

Enforces minimum security standards on user-supplied passwords.
"""

import re


class PasswordValidationError(ValueError):
    """Raised when a password fails complexity checks."""


def validate_password_strength(password: str) -> None:
    """
    Validate that a password meets complexity requirements.

    Rules:
    - At least 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character (!@#$%^&*...)

    Raises:
        PasswordValidationError: If any rule fails.
    """
    errors: list[str] = []

    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("an uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("a lowercase letter")
    if not re.search(r"\d", password):
        errors.append("a digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=$$$$/\\;'`~]", password):
        errors.append("a special character")

    if errors:
        raise PasswordValidationError(f"Password must contain: {', '.join(errors)}")
