"""Google OAuth + session + Traefik forwardAuth."""
from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import time
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from . import config
from .db import db_cursor

router = APIRouter()

# ── Google OAuth endpoints ──────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "openid email profile"


def _sign(data: str) -> str:
    """HMAC-SHA256 signature."""
    return hmac.new(config.SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()


def _error_page(title: str, icon: str, message: str, action_url: str, action_text: str, status: int) -> str:
    """Render a styled error page matching portal design."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — kazusa</title>
  <style>
    :root {{
      --bg: #fafafa; --card-bg: #fff; --border: #e5e7eb; --text: #171717;
      --text-muted: #737373; --text-subtle: #a3a3a3; --accent: #2563eb;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0a0a0a; --card-bg: #171717; --border: #262626; --text: #fafafa;
        --text-muted: #a3a3a3; --text-subtle: #525252; --accent: #60a5fa;
      }}
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      background: var(--bg); color: var(--text); min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
    }}
    .container {{
      text-align: center; padding: 48px 32px; max-width: 400px;
    }}
    .icon {{ font-size: 48px; margin-bottom: 16px; }}
    h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 8px; }}
    p {{ color: var(--text-muted); font-size: 14px; line-height: 1.6; margin-bottom: 24px; }}
    a {{
      display: inline-block; padding: 10px 24px; border-radius: 8px;
      background: var(--accent); color: #fff; text-decoration: none;
      font-size: 14px; font-weight: 500; transition: opacity .15s;
    }}
    a:hover {{ opacity: .85; }}
    .footer {{ margin-top: 32px; font-size: 11px; color: var(--text-subtle); }}
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <a href="{action_url}">{action_text}</a>
    <div class="footer">kazusa home portal</div>
  </div>
</body>
</html>"""


def _make_session_token(user_id: int, email: str) -> str:
    """Create a signed session token: user_id.email.timestamp.signature"""
    ts = str(int(time.time()))
    payload = f"{user_id}.{email}.{ts}"
    sig = _sign(payload)
    return f"{payload}.{sig}"


def _verify_session_token(token: str) -> Optional[dict]:
    """Verify and decode session token. Returns user info or None."""
    # Token format: user_id.email.timestamp.signature
    # Email may contain dots, so split from the right
    try:
        rest, sig = token.rsplit(".", 1)
        rest, ts_str = rest.rsplit(".", 1)
        user_id_str, email = rest.split(".", 1)
    except ValueError:
        return None
    payload = f"{user_id_str}.{email}.{ts_str}"
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    ts = int(ts_str)
    if time.time() - ts > config.MAX_AGE:
        return None
    try:
        user_id = int(user_id_str)
    except ValueError:
        return None
    return {"user_id": user_id, "email": email}


def _get_current_user(request: Request) -> Optional[dict]:
    """Extract user from session cookie."""
    token = request.cookies.get(config.COOKIE)
    if not token:
        return None
    info = _verify_session_token(token)
    if not info:
        return None
    # Fetch fresh user data
    with db_cursor() as cur:
        cur.execute("SELECT id, email, name, picture, role FROM home_users WHERE id = %s", (info["user_id"],))
        user = cur.fetchone()
    return dict(user) if user else None


def _check_acl(email: str, host: str, role: str = "user") -> bool:
    """Check if user is allowed to access host via role ACL then email ACL.
    
    Priority:
    1. home_role_acl — match by (domain, role), role-level bulk authorization
    2. home_acl — match by (domain, email), per-user fine-grained override
    """
    # 1. Check role ACL first
    with db_cursor() as cur:
        cur.execute("SELECT domain, role FROM home_role_acl WHERE enabled = TRUE")
        role_rules = cur.fetchall()
    for rule in role_rules:
        if fnmatch(host, rule["domain"]) and fnmatch(role, rule["role"]):
            return True

    # 2. Fall back to per-email ACL
    with db_cursor() as cur:
        cur.execute("SELECT domain, email FROM home_acl WHERE enabled = TRUE")
        rules = cur.fetchall()
    for rule in rules:
        domain_match = fnmatch(host, rule["domain"])
        email_match = fnmatch(email, rule["email"])
        if domain_match and email_match:
            return True
    return False


# ── OAuth flow ──────────────────────────────────────────

@router.get("/auth/login")
async def auth_login(request: Request):
    """Redirect to Google OAuth."""
    return_url = request.query_params.get("return", config.PORTAL_URL)
    state = _sign(return_url)[:32] + "." + return_url
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = ""):
    """Handle Google OAuth callback."""
    if not code:
        return HTMLResponse("<h1>Missing code</h1>", status_code=400)

    # Parse state to get return URL
    return_url = config.PORTAL_URL
    if "." in state:
        _, return_url = state.split(".", 1)

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            import logging
            logging.error("Token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            return HTMLResponse(f"<h1>Token exchange failed</h1><pre>{token_resp.text}</pre>", status_code=400)

        access_token = token_resp.json()["access_token"]
        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}"
        })
        if userinfo_resp.status_code != 200:
            return HTMLResponse("<h1>Failed to get user info</h1>", status_code=400)

        userinfo = userinfo_resp.json()

    email = userinfo["email"]
    name = userinfo.get("name", "")
    picture = userinfo.get("picture", "")

    # Upsert user
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO home_users (email, name, picture, role, last_login_at)
            VALUES (%s, %s, %s, 'user', now())
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                picture = EXCLUDED.picture,
                last_login_at = now()
            RETURNING id, role
        """, (email, name, picture))
        user = cur.fetchone()
        user_id = user["id"]

        # Ensure admin role
        if email == config.ADMIN_EMAIL:
            cur.execute("UPDATE home_users SET role = 'admin' WHERE id = %s AND role != 'admin'", (user_id,))

        # Clean expired sessions
        cur.execute("DELETE FROM home_sessions WHERE expires_at < now()")

    # Create session token
    token = _make_session_token(user_id, email)

    # Set cookie and redirect
    response = RedirectResponse(return_url)
    response.set_cookie(
        key=config.COOKIE,
        value=token,
        max_age=config.MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        domain=config.COOKIE_DOMAIN if config.COOKIE_DOMAIN else None,
    )
    return response


@router.get("/auth/logout")
async def auth_logout():
    """Clear session and redirect to portal."""
    response = RedirectResponse(config.PORTAL_URL)
    response.delete_cookie(key=config.COOKIE, domain=config.COOKIE_DOMAIN if config.COOKIE_DOMAIN else None)
    return response


@router.get("/auth/me")
async def auth_me(request: Request):
    """Return current user info (JSON)."""
    user = _get_current_user(request)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)
    return {"authenticated": True, **user}


# ── Traefik ForwardAuth ─────────────────────────────────

@router.api_route("/auth/verify", methods=["GET", "HEAD"])
async def auth_verify(request: Request, response: Response):
    """
    Traefik forwardAuth endpoint.
    - 200 + X-User-* headers → allow
    - 401 → redirect to login (for browser requests)
    """
    # Skip auth for the portal itself and auth endpoints
    forwarded_host = request.headers.get("X-Forwarded-Host", "")
    forwarded_uri = request.headers.get("X-Forwarded-Uri", "")
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "https")

    # Allow portal and auth endpoints without auth
    portal_hosts = {h.strip() for h in config.PORTAL_HOSTS.split(",") if h.strip()} if config.PORTAL_HOSTS else set()
    if forwarded_host in portal_hosts:
        return Response(status_code=200)
    if forwarded_uri.startswith("/auth/"):
        return Response(status_code=200)

    # Check session
    user = _get_current_user(request)
    if not user:
        original_url = f"{forwarded_proto}://{forwarded_host}{forwarded_uri}"
        login_url = f"{config.PORTAL_URL}/auth/login?return={original_url}"
        return HTMLResponse(_error_page(
            title="需要登录",
            icon="🔒",
            message="你还未登录，请先登录后再访问此页面。",
            action_url=login_url,
            action_text="使用 Google 账号登录",
            status=401,
        ), status_code=401)

    # Check ACL
    if not _check_acl(user["email"], forwarded_host, user.get("role", "user")):
        return HTMLResponse(_error_page(
            title="无权访问",
            icon="🚫",
            message=f"你的账号 <strong>{html.escape(user['email'])}</strong> 没有访问此应用的权限。<br>如需开通，请联系管理员。",
            action_url=config.PORTAL_URL,
            action_text="返回主页",
            status=403,
        ), status_code=403)

    # Allow — pass user info to upstream
    response.status_code = 200
    response.headers["X-User-Id"] = str(user["id"])
    response.headers["X-User-Email"] = user["email"]
    response.headers["X-User-Name"] = quote(user.get("name") or "")
    response.headers["X-User-Role"] = user.get("role") or "user"
    return response


# ── Admin API ───────────────────────────────────────────

def _require_admin(request: Request) -> Optional[dict]:
    user = _get_current_user(request)
    if not user or user.get("role") != "admin":
        return None
    return user


@router.get("/api/admin/users")
async def list_users(request: Request):
    if not _require_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("SELECT id, email, name, role, created_at, last_login_at FROM home_users ORDER BY id")
        users = [dict(u) for u in cur.fetchall()]
    for u in users:
        for k in ("created_at", "last_login_at"):
            if u[k]:
                u[k] = u[k].isoformat()
    return users


@router.post("/api/admin/users/{user_id}/role")
async def update_user_role(request: Request, user_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    new_role = body.get("role", "user").strip()
    if not new_role:
        return JSONResponse({"error": "role must not be empty"}, status_code=400)
    with db_cursor() as cur:
        cur.execute("UPDATE home_users SET role = %s WHERE id = %s", (new_role, user_id))
    return {"ok": True}


@router.delete("/api/admin/users/{user_id}")
async def delete_user(request: Request, user_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("DELETE FROM home_users WHERE id = %s AND email != %s", (user_id, config.ADMIN_EMAIL))
    return {"ok": True}


@router.get("/api/admin/acl")
async def list_acl(request: Request):
    if not _require_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("SELECT id, domain, email, enabled, created_at FROM home_acl ORDER BY id")
        rules = [dict(r) for r in cur.fetchall()]
    for r in rules:
        if r["created_at"]:
            r["created_at"] = r["created_at"].isoformat()
    return rules


@router.post("/api/admin/acl")
async def create_acl(request: Request):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    domain = body.get("domain", "").strip()
    email = body.get("email", "").strip()
    if not domain or not email:
        return JSONResponse({"error": "domain and email required"}, status_code=400)
    with db_cursor() as cur:
        cur.execute("INSERT INTO home_acl (domain, email) VALUES (%s, %s) RETURNING id", (domain, email))
        rule_id = cur.fetchone()["id"]
    return {"id": rule_id, "domain": domain, "email": email, "enabled": True}


@router.put("/api/admin/acl/{rule_id}")
async def update_acl(request: Request, rule_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    with db_cursor() as cur:
        if "enabled" in body:
            cur.execute("UPDATE home_acl SET enabled = %s WHERE id = %s", (body["enabled"], rule_id))
        if "domain" in body:
            cur.execute("UPDATE home_acl SET domain = %s WHERE id = %s", (body["domain"], rule_id))
        if "email" in body:
            cur.execute("UPDATE home_acl SET email = %s WHERE id = %s", (body["email"], rule_id))
    return {"ok": True}


@router.delete("/api/admin/acl/{rule_id}")
async def delete_acl(request: Request, rule_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("DELETE FROM home_acl WHERE id = %s", (rule_id,))
    return {"ok": True}


# ── Role ACL Admin API ──────────────────────────────────

@router.get("/api/admin/role-acl")
async def list_role_acl(request: Request):
    if not _require_admin(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("SELECT id, domain, role, enabled, created_at FROM home_role_acl ORDER BY id")
        rules = [dict(r) for r in cur.fetchall()]
    for r in rules:
        if r["created_at"]:
            r["created_at"] = r["created_at"].isoformat()
    return rules


@router.post("/api/admin/role-acl")
async def create_role_acl(request: Request):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    domain = body.get("domain", "").strip()
    role = body.get("role", "").strip()
    if not domain or not role:
        return JSONResponse({"error": "domain and role required"}, status_code=400)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO home_role_acl (domain, role) VALUES (%s, %s) RETURNING id",
            (domain, role),
        )
        rule_id = cur.fetchone()["id"]
    return {"id": rule_id, "domain": domain, "role": role, "enabled": True}


@router.put("/api/admin/role-acl/{rule_id}")
async def update_role_acl(request: Request, rule_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    body = await request.json()
    with db_cursor() as cur:
        if "enabled" in body:
            cur.execute("UPDATE home_role_acl SET enabled = %s WHERE id = %s", (body["enabled"], rule_id))
        if "domain" in body:
            cur.execute("UPDATE home_role_acl SET domain = %s WHERE id = %s", (body["domain"], rule_id))
        if "role" in body:
            cur.execute("UPDATE home_role_acl SET role = %s WHERE id = %s", (body["role"], rule_id))
    return {"ok": True}


@router.delete("/api/admin/role-acl/{rule_id}")
async def delete_role_acl(request: Request, rule_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    with db_cursor() as cur:
        cur.execute("DELETE FROM home_role_acl WHERE id = %s", (rule_id,))
    return {"ok": True}
