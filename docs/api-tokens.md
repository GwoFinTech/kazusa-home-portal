## home_api_tokens

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| id | SERIAL PK | auto | |
| user_id | INTEGER FK → home_users | | ON DELETE CASCADE |
| token_hash | TEXT UNIQUE NOT NULL | | SHA256 of the raw token |
| description | TEXT | `''` | User-given name |
| prefix | TEXT NOT NULL | | First 11 chars (`hp_xxxxxx`) for UI display |
| expires_at | TIMESTAMPTZ | NULL | NULL = never expires |
| last_used_at | TIMESTAMPTZ | NULL | Updated on each auth via `_get_user_by_bearer()` |
| created_at | TIMESTAMPTZ | `now()` | |
| revoked | BOOLEAN | `false` | Soft revoke |

Token format: `hp_<secrets.token_urlsafe(32)>`. SHA256 hashed in DB. Full token shown only once at creation.

Auth flow: `Authorization: Bearer <token>` → `_get_current_user()` + `/auth/verify` (forwardAuth).
