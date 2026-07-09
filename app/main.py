"""home-portal — Docker-label service dashboard + auth gateway."""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlparse

import docker
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from .auth import router as auth_router, _get_current_user, _check_acl, _csrf_token, limiter as auth_limiter
from .db import init_pool, close_pool
from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Label schema ─────────────────────────────────────────
LABEL_PREFIX = "homepage"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@dataclass
class ServiceEntry:
    name: str
    title: str
    description: str
    icon: str
    url: str
    host: str = ""
    category: str = ""
    order: int = 100
    status: str = "running"


def _extract_host_from_traefik(labels: dict) -> Optional[str]:
    for k, v in labels.items():
        if "rule" in k and "Host(" in v:
            m = re.search(r"Host\(`([^`]+)`\)", v)
            if m:
                return m.group(1)
    return None


def _fetch_services() -> list[ServiceEntry]:
    """Discover services from Docker API (expensive call)."""
    try:
        client = docker.from_env()
    except Exception:
        return []

    services: list[ServiceEntry] = []
    for c in client.containers.list():
        labels = c.labels or {}
        if labels.get(f"{LABEL_PREFIX}.enable") != "true":
            continue

        host = _extract_host_from_traefik(labels)
        url = labels.get(f"{LABEL_PREFIX}.url", "")
        if not url and host:
            url = f"https://{host}"

        services.append(ServiceEntry(
            name=c.name or "unknown",
            title=labels.get(f"{LABEL_PREFIX}.title", c.name or "Unknown"),
            description=labels.get(f"{LABEL_PREFIX}.description", ""),
            icon=labels.get(f"{LABEL_PREFIX}.icon", "\\U0001f310"),
            url=url,
            host=host or "",
            category=labels.get(f"{LABEL_PREFIX}.category", ""),
            order=int(labels.get(f"{LABEL_PREFIX}.order", "100")),
            status=c.status,
        ))

    services.sort(key=lambda s: (s.order, s.title))
    return services


# ── Service cache (TTL + background refresh) ───────────

class _ServiceCache:
    """Thread-safe cache with TTL and background refresh."""

    def __init__(self, ttl: int = 30):
        self.ttl = ttl
        self._data: list[ServiceEntry] = []
        self._ts: float = 0
        self._lock = threading.Lock()
        self._refreshing = False

    def get(self) -> list[ServiceEntry]:
        now = time.time()
        if now - self._ts < self.ttl:
            return self._data
        # Stale — trigger async refresh, return stale data
        if not self._refreshing:
            self._refreshing = True
            threading.Thread(target=self._refresh, daemon=True).start()
        return self._data

    def _refresh(self):
        try:
            data = _fetch_services()
            with self._lock:
                self._data = data
                self._ts = time.time()
        except Exception as e:
            logger.warning("Service cache refresh failed: %s", e)
        finally:
            self._refreshing = False

    def invalidate(self):
        with self._lock:
            self._ts = 0


_svc_cache = _ServiceCache(ttl=30)


def discover_services() -> list[ServiceEntry]:
    return _svc_cache.get()


# ── Rate limiter ───────────────────────────────────────

limiter = auth_limiter


# ── FastAPI ──────────────────────────────────────────────

app = FastAPI(title="home-portal", version="2.1.0")

# CORS — restrict to portal domain
_cors_origins: list[str] = []
if config.PORTAL_URL:
    parsed = urlparse(config.PORTAL_URL)
    _cors_origins.append(f"{parsed.scheme}://{parsed.netloc}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:8000"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
    allow_credentials=True,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        {"error": "rate_limit_exceeded", "detail": str(exc)},
        status_code=429,
    )


# Mount auth router
app.include_router(auth_router)

# ── Lifecycle ──────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    init_pool()
    # Warm up service cache
    _svc_cache._refresh()
    logger.info("Service cache warmed, pool initialized")


@app.on_event("shutdown")
def on_shutdown():
    close_pool()


@app.get("/api/services")
@limiter.limit("60/minute")
def list_services(request: Request):
    user = _get_current_user(request)
    services = discover_services()
    result = []
    for s in services:
        d = asdict(s)
        if not user:
            d["access"] = "unauthenticated"
        elif not s.host:
            d["access"] = "allowed"
        elif _check_acl(user["email"], s.host, user.get("role", "user")):
            d["access"] = "allowed"
        else:
            d["access"] = "denied"
        result.append(d)
    return JSONResponse(content=result, headers={"Cache-Control": "private, no-store"})


@app.get("/api/me")
def api_me(request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-cache"})
    session_token = request.cookies.get(config.COOKIE, "")
    csrf = _csrf_token(session_token) if session_token else ""
    return JSONResponse({"authenticated": True, "csrf": csrf, **user}, headers={"Cache-Control": "no-cache"})


# ── Static pages ─────────────────────────────────────────

@app.get("/")
def index(request: Request):
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))


@app.get("/admin")
def admin_page(request: Request):
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


@app.get("/account/tokens")
def tokens_page(request: Request):
    return FileResponse(os.path.join(STATIC_DIR, "tokens.html"))


@app.get("/common.css")
def common_css():
    return FileResponse(os.path.join(STATIC_DIR, "common.css"), media_type="text/css")


@app.get("/common.js")
def common_js():
    return FileResponse(os.path.join(STATIC_DIR, "common.js"), media_type="application/javascript")


@app.get("/manifest.json")
def manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"), media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")


# Mount static assets
_assets = os.path.join(STATIC_DIR, "assets")
if os.path.isdir(_assets):
    app.mount("/assets", StaticFiles(directory=_assets), name="assets")
