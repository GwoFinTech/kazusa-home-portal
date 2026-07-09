-- Migration 002: home_api_tokens
-- Personal API tokens for programmatic access to *.kazusa.feng.moe services

CREATE TABLE IF NOT EXISTS home_api_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES home_users(id) ON DELETE CASCADE,
    token_hash  TEXT UNIQUE NOT NULL,            -- SHA256(raw_token)
    description TEXT NOT NULL DEFAULT '',
    prefix      TEXT NOT NULL,                   -- first 8 chars for UI display
    expires_at  TIMESTAMPTZ DEFAULT NULL,        -- NULL = never expires
    last_used_at TIMESTAMPTZ DEFAULT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    revoked     BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON home_api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON home_api_tokens(user_id);
