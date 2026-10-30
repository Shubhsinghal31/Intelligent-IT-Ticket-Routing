-- ============================================================
-- Migration: 008_create_attachments_table.sql
-- Purpose : File attachments on tickets (metadata only)
-- ============================================================

CREATE TABLE attachments (
    id               SERIAL PRIMARY KEY,
    ticket_id        INTEGER      NOT NULL,
    uploaded_by_id   INTEGER      NOT NULL,
    file_name        VARCHAR(255) NOT NULL,
    file_path        VARCHAR(500) NOT NULL,
    mime_type        VARCHAR(100) NOT NULL,
    file_size_bytes  BIGINT       NOT NULL,
    uploaded_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_attachments_ticket 
        FOREIGN KEY (ticket_id) 
        REFERENCES tickets(id)
        ON DELETE CASCADE,
    
    CONSTRAINT fk_attachments_user 
        FOREIGN KEY (uploaded_by_id) 
        REFERENCES users(id)
        ON DELETE RESTRICT,
    
    CONSTRAINT chk_attachments_file_size_positive 
        CHECK (file_size_bytes > 0),
    
    CONSTRAINT chk_attachments_file_size_max 
        CHECK (file_size_bytes <= 10485760)  -- 10 MB
);

COMMENT ON TABLE  attachments                  IS 'File metadata; actual files stored on disk/S3';
COMMENT ON COLUMN attachments.file_path        IS 'Relative path or S3 key';
COMMENT ON COLUMN attachments.file_size_bytes  IS 'Max 10 MB enforced at DB level';