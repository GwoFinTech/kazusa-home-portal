"""home-portal — Docker-label service dashboard + auth gateway."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Optional

import docker
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import router as auth_router, _get_current_user, _check_acl
from . import config

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


def discover_services() -> list[ServiceEntry]:
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


# ── FastAPI ──────────────────────────────────────────────

app = FastAPI(title="home-portal", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount auth router
app.include_router(auth_router)


@app.get("/api/services")
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
    return result


@app.get("/api/me")
def api_me(request: Request):
    user = _get_current_user(request)
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, **user}


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


# Mount static assets
_assets = os.path.join(STATIC_DIR, "assets")
if os.path.isdir(_assets):
    app.mount("/assets", StaticFiles(directory=_assets), name="assets")
