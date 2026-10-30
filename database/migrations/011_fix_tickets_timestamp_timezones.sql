-- ============================================================
-- Migration: 011_fix_tickets_timestamp_timezones.sql
-- Purpose : Align tickets' timestamp columns with the ORM model
--           and with how the application actually uses them.
--
-- Bug this fixes:
--   006_create_tickets_table.sql declared created_at, updated_at,
--   resolved_at, closed_at, and sla_due_at as plain TIMESTAMP
--   (timezone-naive). backend/models/ticket.py's TimestampMixin
--   already declared created_at/updated_at as DateTime(timezone=True)
--   — drift between the migration and the model that had gone
--   unnoticed because nothing compared those two columns directly.
--
--   TicketService, however, works entirely in timezone-aware UTC:
--   resolve_ticket()/close_ticket() stamp resolved_at/closed_at with
--   datetime.now(timezone.utc), and create_ticket() derives
--   sla_due_at from created_at + timedelta. Storing those aware
--   values into naive TIMESTAMP columns silently strips the
--   timezone on the next read (e.g. session.refresh(), or any fresh
--   fetch of the ticket). The moment resolve_ticket() then compared
--   a freshly-read (now-naive) sla_due_at against a still-aware
--   resolved_at, Python raised:
--     TypeError: can't compare offset-naive and offset-aware datetimes
--   This only surfaces once there's a real Postgres round trip
--   between setting sla_due_at and reading it back — which is
--   exactly what integration tests exercise and unit tests (fully
--   mocked, no DB) do not.
--
-- USING clauses assume existing naive timestamps represent UTC
-- (true here: CURRENT_TIMESTAMP and the app's own datetime.utcnow()/
-- datetime.now(timezone.utc) calls are already UTC) — this is a
-- type change, not a value shift.
-- ============================================================

ALTER TABLE tickets
    ALTER COLUMN created_at  TYPE TIMESTAMPTZ USING created_at  AT TIME ZONE 'UTC',
    ALTER COLUMN updated_at  TYPE TIMESTAMPTZ USING updated_at  AT TIME ZONE 'UTC',
    ALTER COLUMN resolved_at TYPE TIMESTAMPTZ USING resolved_at AT TIME ZONE 'UTC',
    ALTER COLUMN closed_at   TYPE TIMESTAMPTZ USING closed_at   AT TIME ZONE 'UTC',
    ALTER COLUMN sla_due_at  TYPE TIMESTAMPTZ USING sla_due_at  AT TIME ZONE 'UTC';

COMMENT ON COLUMN tickets.sla_due_at IS 'Deadline derived from sla_policy.resolution_time_hours (UTC, timezone-aware)';
