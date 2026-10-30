-- ============================================================
-- Migration: 002_create_roles_table.sql
-- Purpose : Stores user roles for RBAC (Role-Based Access Control)
-- ============================================================

CREATE TABLE roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_role_name_lowercase CHECK (name = LOWER(name))
);

COMMENT ON TABLE  roles               IS 'User roles: admin, engineer, employee';
COMMENT ON COLUMN roles.name          IS 'Unique role identifier, lowercase';
COMMENT ON COLUMN roles.description   IS 'Human-readable role purpose';