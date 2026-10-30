"""rename comments columns: user_id -> author_id, content -> body

Revision ID: a3f8c2d91e05
Revises: 879b53d74f82
Create Date: 2026-06-28
"""

from alembic import op

revision = "a3f8c2d91e05"
down_revision = "879b53d74f82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safe in-place rename — zero data loss, instant even on large tables
    op.alter_column("comments", "user_id", new_column_name="author_id")
    op.alter_column("comments", "content", new_column_name="body")

    # Rename the FK constraint to match the new column name
    op.drop_constraint("fk_comments_user", "comments", type_="foreignkey")
    op.create_foreign_key(
        "fk_comments_author",
        "comments",
        "users",
        ["author_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_comments_author", "comments", type_="foreignkey")
    op.create_foreign_key(
        "fk_comments_user",
        "comments",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("comments", "author_id", new_column_name="user_id")
    op.alter_column("comments", "body", new_column_name="content")
