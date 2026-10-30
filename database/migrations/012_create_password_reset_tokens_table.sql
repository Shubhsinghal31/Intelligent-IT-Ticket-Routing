-- ============================================================
-- Migration: 012_create_password_reset_tokens_table.sql
-- Purpose : Supports the Forgot Password flow with single-use,
--           expiring, hashed reset tokens.
--
-- Design notes:
--   - token_hash, not token: the raw token is a high-entropy random
--     value (32 bytes from Python's `secrets` module) emailed to the
--     user. Only its SHA-256 hash is stored, mirroring the same
--     principle as password_hash on users — if this table leaks, the
--     tokens inside it are useless without the original value.
--   - used_at (nullable): NULL means still valid/unused. Set once,
--     at the moment the token is redeemed, so it can never be reused
--     even within its expiry window (protects against a reset link
--     being replayed if it leaked via logs, browser history, etc).
--   - ON DELETE CASCADE: if a user is deleted, their outstanding
--     reset tokens are meaningless and should disappear with them.
-- ============================================================

CREATE TABLE password_reset_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,  -- hex-encoded SHA-256 = 64 chars
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_password_reset_tokens_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);

COMMENT ON TABLE  password_reset_tokens             IS 'Single-use, expiring tokens for the Forgot Password flow';
COMMENT ON COLUMN password_reset_tokens.token_hash  IS 'SHA-256 hex digest of the raw token emailed to the user — raw value is never stored';
COMMENT ON COLUMN password_reset_tokens.used_at     IS 'Set once redeemed; NULL means still valid. Prevents replay even before expiry.';
