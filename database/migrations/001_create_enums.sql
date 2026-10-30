-- ============================================================
-- Migration: 001_create_enums.sql
-- Purpose : Define PostgreSQL ENUM types for stable value sets
-- Author  : Saumay Ashish
-- Date    : 2026-06-26
-- ============================================================

-- Ticket lifecycle states
CREATE TYPE ticket_status AS ENUM (
    'open',          -- newly created
    'in_progress',   -- engineer working on it
    'on_hold',       -- waiting for user response
    'resolved',      -- engineer marked done
    'closed',        -- user confirmed closure
    'reopened'       -- user reopened after closure
);

-- Ticket urgency levels
CREATE TYPE ticket_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- Add comments for documentation (visible in DBeaver)
COMMENT ON TYPE ticket_status IS 'Lifecycle states a ticket can move through';
COMMENT ON TYPE ticket_priority IS 'Urgency classification; drives SLA timer';