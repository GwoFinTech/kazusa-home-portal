-- Migration 001: initial schema
-- Creates the core tables for users, sessions, ACL, audit log and announcements.

CREATE TABLE IF NOT EXISTS home_users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    name          TEXT,
    picture       TEXT,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS home_sessions (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES home_users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_home_sessions_expires ON home_sessions(expires_at);

CREATE TABLE IF NOT EXISTS home_acl (
    id         SERIAL PRIMARY KEY,
    domain     TEXT NOT NULL,
    email      TEXT NOT NULL,
    enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS home_role_acl (
    id         SERIAL PRIMARY KEY,
    domain     TEXT NOT NULL,
    role       TEXT NOT NULL,
    enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT home_role_acl_domain_role_unique UNIQUE (domain, role)
);

CREATE TABLE IF NOT EXISTS home_role_presets (
    id         SERIAL PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    role       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS home_audit_log (
    id          SERIAL PRIMARY KEY,
    actor_email TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT '',
    details     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS home_announcements (
    id         SERIAL PRIMARY KEY,
    message    TEXT NOT NULL,
    level      TEXT NOT NULL DEFAULT 'info',
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
