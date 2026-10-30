-- ============================================================
-- Migration: 005_create_sla_policies_table.sql
-- Purpose : Stores SLA rules per priority level
-- ============================================================

CREATE TABLE sla_policies (
    id                       SERIAL PRIMARY KEY,
    priority                 ticket_priority NOT NULL UNIQUE,
    response_time_hours      INTEGER NOT NULL,
    resolution_time_hours    INTEGER NOT NULL,
    description              TEXT,
    created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_sla_response_positive 
        CHECK (response_time_hours > 0),
    
    CONSTRAINT chk_sla_resolution_positive 
        CHECK (resolution_time_hours > 0),
    
    CONSTRAINT chk_sla_response_lte_resolution
        CHECK (response_time_hours <= resolution_time_hours)
);

COMMENT ON TABLE  sla_policies                       IS 'SLA targets per priority level';
COMMENT ON COLUMN sla_policies.response_time_hours   IS 'Max hours to first response';
COMMENT ON COLUMN sla_policies.resolution_time_hours IS 'Max hours to full resolution';