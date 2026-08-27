-- Migration 004: home_manual_services
-- Manual service registry for Traefik routes that are NOT backed by Docker
-- labels (e.g. /opt/traefik/dynamic/*.yml file providers like dsh / hermes-dashboard).
-- These are merged into the service list alongside Docker-label-discovered services.

CREATE TABLE IF NOT EXISTS home_manual_services (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    icon        TEXT NOT NULL DEFAULT '📁',
    url         TEXT NOT NULL DEFAULT '',
    host        TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 100,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
