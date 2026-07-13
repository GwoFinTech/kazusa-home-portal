-- Migration 003: session metadata
-- Adds IP, user-agent and last-used tracking so users can manage active devices.

ALTER TABLE home_sessions
    ADD COLUMN IF NOT EXISTS ip_addr TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS user_agent TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_home_sessions_user_id ON home_sessions(user_id);
