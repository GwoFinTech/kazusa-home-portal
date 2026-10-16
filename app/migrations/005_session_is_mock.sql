-- Migration 005: session pool separation
-- Mark mock-login sessions so automated logins are capped in their own pool
-- and can never evict an interactive browser session.

ALTER TABLE home_sessions
    ADD COLUMN IF NOT EXISTS is_mock BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_home_sessions_user_mock
    ON home_sessions(user_id, is_mock, created_at DESC);
