-- ============================================================
-- Migration: 010_create_indexes.sql
-- Purpose : Indexes for query performance
-- Note    : PK and UNIQUE constraints already create indexes;
--           these are SUPPLEMENTAL indexes for common queries.
-- ============================================================

-- USERS: lookup by email/username (login) - already UNIQUE-indexed
-- But add index on role_id for "list all engineers" queries
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_department_id ON users(department_id);
CREATE INDEX idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

-- TICKETS: most-queried table — needs many indexes
CREATE INDEX idx_tickets_status              ON tickets(status);
CREATE INDEX idx_tickets_priority            ON tickets(priority);
CREATE INDEX idx_tickets_created_by_id       ON tickets(created_by_id);
CREATE INDEX idx_tickets_assigned_to_id      ON tickets(assigned_to_id);
CREATE INDEX idx_tickets_department_id       ON tickets(department_id);
CREATE INDEX idx_tickets_created_at          ON tickets(created_at DESC);
CREATE INDEX idx_tickets_sla_due_at          ON tickets(sla_due_at);
CREATE INDEX idx_tickets_sla_breached        ON tickets(sla_breached) WHERE sla_breached = TRUE;

-- Composite index for dashboard query: "Open tickets per department"
CREATE INDEX idx_tickets_status_department   ON tickets(status, department_id);

-- COMMENTS: fetch comments by ticket
CREATE INDEX idx_comments_ticket_id ON comments(ticket_id);
CREATE INDEX idx_comments_user_id   ON comments(user_id);

-- ATTACHMENTS
CREATE INDEX idx_attachments_ticket_id ON attachments(ticket_id);

-- TICKET HISTORY: timeline view
CREATE INDEX idx_history_ticket_id    ON ticket_history(ticket_id);
CREATE INDEX idx_history_changed_at   ON ticket_history(changed_at DESC);