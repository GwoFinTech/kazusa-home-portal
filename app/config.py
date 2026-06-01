"""Environment-based configuration."""
import os

# ── Google OAuth ──
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

# ── Session ──
SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "86400"))  # 24h
COOKIE = "hp_session"
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")

# ── Admin ──
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")

# ── DB ──
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "kazusa_home")
DB_USER = os.getenv("DB_USER", "postgres")

# ── Portal ──
PORTAL_URL = os.getenv("PORTAL_URL", "http://localhost:8000")
# Comma-separated list of hosts that bypass auth (portal domains)
PORTAL_HOSTS = os.getenv("PORTAL_HOSTS", "")
