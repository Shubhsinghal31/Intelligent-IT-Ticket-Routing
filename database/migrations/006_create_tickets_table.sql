-- ============================================================
-- Migration: 006_create_tickets_table.sql
-- Purpose : Core tickets table — heart of the ITSM system
-- ============================================================

CREATE TABLE tickets (
    id                          SERIAL PRIMARY KEY,
    ticket_number               VARCHAR(20)  NOT NULL UNIQUE,
    title                       VARCHAR(200) NOT NULL,
    description                 TEXT         NOT NULL,
    
    -- Lifecycle
    status                      ticket_status   NOT NULL DEFAULT 'open',
    priority                    ticket_priority NOT NULL DEFAULT 'medium',
    
    -- Relationships
    created_by_id               INTEGER NOT NULL,
    assigned_to_id              INTEGER,
    department_id               INTEGER,
    sla_policy_id               INTEGER,
    
    -- Timestamps
    created_at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at                 TIMESTAMP,
    closed_at                   TIMESTAMP,
    sla_due_at                  TIMESTAMP,
    
    -- SLA tracking
    sla_breached                BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- ML predictions (populated by services on ticket creation)
    predicted_priority_score    DECIMAL(5, 4),
    predicted_sla_breach_prob   DECIMAL(5, 4),
    predicted_resolution_hours  DECIMAL(8, 2),
    
    -- Foreign keys
    CONSTRAINT fk_tickets_created_by 
        FOREIGN KEY (created_by_id) 
        REFERENCES users(id)
        ON DELETE RESTRICT,
    
    CONSTRAINT fk_tickets_assigned_to 
        FOREIGN KEY (assigned_to_id) 
        REFERENCES users(id)
        ON DELETE SET NULL,
    
    CONSTRAINT fk_tickets_department 
        FOREIGN KEY (department_id) 
        REFERENCES departments(id)
        ON DELETE SET NULL,
    
    CONSTRAINT fk_tickets_sla_policy 
        FOREIGN KEY (sla_policy_id) 
        REFERENCES sla_policies(id)
        ON DELETE SET NULL,
    
    -- Business rule checks
    CONSTRAINT chk_tickets_title_length 
        CHECK (LENGTH(TRIM(title)) >= 5),
    
    CONSTRAINT chk_tickets_description_length 
        CHECK (LENGTH(TRIM(description)) >= 10),
    
    CONSTRAINT chk_tickets_resolved_after_created
        CHECK (resolved_at IS NULL OR resolved_at >= created_at),
    
    CONSTRAINT chk_tickets_closed_after_resolved
        CHECK (closed_at IS NULL OR resolved_at IS NULL OR closed_at >= resolved_at),
    
    CONSTRAINT chk_tickets_predicted_priority_range
        CHECK (predicted_priority_score IS NULL 
               OR (predicted_priority_score >= 0 AND predicted_priority_score <= 1)),
    
    CONSTRAINT chk_tickets_predicted_sla_range
        CHECK (predicted_sla_breach_prob IS NULL 
               OR (predicted_sla_breach_prob >= 0 AND predicted_sla_breach_prob <= 1))
);

COMMENT ON TABLE  tickets                           IS 'Core ticket entity — drives the ITSM workflow';
COMMENT ON COLUMN tickets.ticket_number             IS 'Human-friendly ID like TKT-2025-00001';
COMMENT ON COLUMN tickets.sla_due_at                IS 'Deadline derived from sla_policy.resolution_time_hours';
COMMENT ON COLUMN tickets.predicted_priority_score  IS 'ML probability that priority should be HIGH; 0–1';
COMMENT ON COLUMN tickets.predicted_sla_breach_prob IS 'ML probability of SLA breach; 0–1';
COMMENT ON COLUMN tickets.predicted_resolution_hours IS 'ML-predicted resolution time in hours';