"""create password_reset_tokens table

Revision ID: c58ea2f7d144
Revises: b47d9a1e6c33
Create Date: 2026-07-02

Mirrors database/migrations/012_create_password_reset_tokens_table.sql —
see that file's header comment for the design rationale (hashed token
storage, single-use via used_at, cascade delete with the owning user).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c58ea2f7d144"
down_revision: str | None = "b47d9a1e6c33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("idx_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("idx_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
