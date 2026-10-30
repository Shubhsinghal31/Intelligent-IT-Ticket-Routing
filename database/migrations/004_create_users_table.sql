-- ============================================================
-- Migration: 004_create_users_table.sql
-- Purpose : Stores user accounts with auth credentials
-- ============================================================

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100) NOT NULL,
    role_id         INTEGER      NOT NULL,
    department_id   INTEGER,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMP,

    CONSTRAINT fk_users_role 
        FOREIGN KEY (role_id) 
        REFERENCES roles(id)
        ON DELETE RESTRICT,
    
    CONSTRAINT fk_users_department 
        FOREIGN KEY (department_id) 
        REFERENCES departments(id)
        ON DELETE SET NULL,
    
    CONSTRAINT chk_users_email_format 
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    
    CONSTRAINT chk_users_username_format
        CHECK (username ~* '^[a-z0-9_]{3,50}$')
);

COMMENT ON TABLE  users                  IS 'User accounts (admins, engineers, employees)';
COMMENT ON COLUMN users.password_hash    IS 'bcrypt hash; never plain text';
COMMENT ON COLUMN users.department_id    IS 'For engineers: which dept they handle. NULL for employees';
COMMENT ON COLUMN users.last_login_at    IS 'Last successful login timestamp; for audit';