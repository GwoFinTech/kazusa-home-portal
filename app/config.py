"""Environment-based configuration."""
import os
import sys

# ── Google OAuth ──
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

# ── Session ──
SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
if SECRET == "change-me-in-production":
    print("FATAL: SESSION_SECRET is set to the default value. "
          "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\"", file=sys.stderr)
    sys.exit(1)
MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "86400"))  # 24h
COOKIE = "hp_session"
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")

# Session caps — enforced in _make_session_token(). Interactive sessions are
# capped per client (user_agent) so one churning device cannot evict sessions
# of other devices; mock-login sessions live in a separate pool.
SESSION_CAP_PER_CLIENT = int(os.getenv("SESSION_CAP_PER_CLIENT", "10"))
SESSION_CAP_PER_USER = int(os.getenv("SESSION_CAP_PER_USER", "100"))
SESSION_CAP_MOCK = int(os.getenv("SESSION_CAP_MOCK", "30"))

# ── Verify signing ──
# Shared secret for HMAC-signed /auth/verify responses (dsh privileged-auth-http
# verifySecret protocol). Empty = unsigned plain-header mode (backward compatible).
VERIFY_SECRET = os.getenv("VERIFY_SECRET", "")

# ── Admin ──
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

# ── DB ──
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "kazusa_home")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# ── Portal ──
PORTAL_URL = os.getenv("PORTAL_URL", "http://localhost:8000")
# Comma-separated list of hosts that bypass auth (portal domains)
PORTAL_HOSTS = os.getenv("PORTAL_HOSTS", "")
