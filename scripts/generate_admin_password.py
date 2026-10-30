"""
Generate a bcrypt hash for the default admin password.

Usage:
    python scripts/generate_admin_password.py
"""

from backend.core.security import hash_password

password = "Admin@12345"

hashed = hash_password(password)

print(f"Password: {password}")
print(f"Hash:     {hashed}")
print()
print("SQL to update admin user:")
print(f"UPDATE users " f"SET password_hash = '{hashed}' " f"WHERE email = 'admin@helpdesk.local';")
