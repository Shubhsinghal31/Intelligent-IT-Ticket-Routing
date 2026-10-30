# 🗄️ Database Layer — helpdesk-ai

## Overview

PostgreSQL schema for the Helpdesk-AI ITSM system. Designed in **3NF** (third normal form) with audit logging and ML prediction columns.

## Tables

| Table | Purpose |
|---|---|
| `roles` | RBAC roles (admin, engineer, employee) |
| `departments` | Teams handling tickets |
| `users` | Authenticated accounts |
| `sla_policies` | SLA targets per priority |
| `tickets` | Core ticket entity |
| `comments` | Discussion threads |
| `attachments` | File metadata |
| `ticket_history` | Audit log |

## Setup

### 1. Create database
\`\`\`sql
CREATE DATABASE helpdesk_ai;
\`\`\`

### 2. Run migrations (in order)
Execute each file in `migrations/` sequentially:
\`\`\`
001_create_enums.sql
002_create_roles_table.sql
... up to ...
010_create_indexes.sql
\`\`\`

### 3. Run seeds
Execute each file in `seeds/`:
\`\`\`
001_seed_roles.sql
002_seed_departments.sql
003_seed_sla_policies.sql
004_seed_admin_user.sql
\`\`\`

### 4. Verify
\`\`\`sql
SELECT COUNT(*) FROM roles;          -- expect 3
SELECT COUNT(*) FROM departments;    -- expect 6
SELECT COUNT(*) FROM sla_policies;   -- expect 4
SELECT COUNT(*) FROM users;          -- expect 1 (admin)
\`\`\`

## ER Diagram

See `docs/architecture/er_diagram.md`.

## Notes

- Migrations are currently **manual SQL**. Milestone 2 will integrate **Alembic** for automated migrations via SQLAlchemy.
- Default admin password (`Admin@12345`) must be changed in production.
