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

Auth flow: `Authorization: Bearer ***` → `_get_current_user()` + `/auth/verify` (forwardAuth).

## Usage

Create a token from `/account/tokens`, then use it as a Bearer token:

```bash
curl -H "Authorization: Bearer hp_xxx...xxx" \
  https://kazusa.feng.moe/api/me
```

Available endpoints (examples):
- `GET /api/me` — current user info
- `GET /api/services` — services and access status
- `GET /auth/tokens` / `POST /auth/tokens` / `DELETE /auth/tokens/{id}` — token management

Notes:
- No CSRF token required for Bearer auth.
- Bearer auth and session cookie are mutually exclusive; only one is needed.
- Tokens are soft-revoked via `revoked=true`; revoked/expired tokens are rejected immediately.
- `last_used_at` is updated on every successful Bearer authentication.
