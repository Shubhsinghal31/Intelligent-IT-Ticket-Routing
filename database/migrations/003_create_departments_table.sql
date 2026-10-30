-- ============================================================
-- Migration: 003_create_departments_table.sql
-- Purpose : Stores departments that handle tickets
-- ============================================================

CREATE TABLE departments (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  departments              IS 'Departments handling tickets (IT, HR, Network, etc.)';
COMMENT ON COLUMN departments.is_active    IS 'Soft-delete flag; inactive depts hidden from UI';