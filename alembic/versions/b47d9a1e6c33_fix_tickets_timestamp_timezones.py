"""fix tickets timestamp columns to be timezone-aware

Revision ID: b47d9a1e6c33
Revises: a3f8c2d91e05
Create Date: 2026-07-02

Mirrors database/migrations/011_fix_tickets_timestamp_timezones.sql — see
that file's header comment for the full bug explanation. Short version:
TicketService works entirely in timezone-aware UTC (datetime.now(timezone.
utc)), but these five columns were TIMESTAMP WITHOUT TIME ZONE, so any
value read back from Postgres came back naive and blew up comparing
against a still-aware in-memory value the moment a real round trip
happened (session.refresh(), a fresh fetch, etc).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b47d9a1e6c33"
down_revision: str | None = "a3f8c2d91e05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ["created_at", "updated_at", "resolved_at", "closed_at", "sla_due_at"]


def upgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "tickets",
            column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.alter_column(
            "tickets",
            column,
            type_=sa.DateTime(timezone=False),
        )
