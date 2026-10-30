-- ============================================================
-- Migration: 009_create_ticket_history_table.sql
-- Purpose : Audit trail for every ticket change
-- ============================================================

CREATE TABLE ticket_history (
    id              SERIAL PRIMARY KEY,
    ticket_id       INTEGER      NOT NULL,
    changed_by_id   INTEGER      NOT NULL,
    field_changed   VARCHAR(50)  NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_history_ticket 
        FOREIGN KEY (ticket_id) 
        REFERENCES tickets(id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_history_user 
        FOREIGN KEY (changed_by_id) 
        REFERENCES users(id)
        ON DELETE RESTRICT
);

COMMENT ON TABLE  ticket_history                IS 'Immutable audit log of all ticket changes';
COMMENT ON COLUMN ticket_history.field_changed  IS 'Column name that changed, e.g. status, priority';
COMMENT ON COLUMN ticket_history.old_value      IS 'Value before change (as string)';
COMMENT ON COLUMN ticket_history.new_value      IS 'Value after change (as string)';