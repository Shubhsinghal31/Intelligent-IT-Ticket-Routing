-- ============================================================
-- Migration: 007_create_comments_table.sql
-- Purpose : Discussion thread attached to tickets
-- ============================================================

CREATE TABLE comments (
    id           SERIAL PRIMARY KEY,
    ticket_id    INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    is_internal  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_comments_ticket 
        FOREIGN KEY (ticket_id) 
        REFERENCES tickets(id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_comments_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(id)
        ON DELETE RESTRICT,
    
    CONSTRAINT chk_comments_content_not_empty 
        CHECK (LENGTH(TRIM(content)) > 0)
);

COMMENT ON TABLE  comments              IS 'Discussion thread on tickets';
COMMENT ON COLUMN comments.is_internal  IS 'TRUE = visible only to engineers/admins';