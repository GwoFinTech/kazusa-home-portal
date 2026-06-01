"""home-portal — lightweight Docker-label-based service dashboard."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Optional

import docker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── Label schema ─────────────────────────────────────────
# homepage.enable     = "true"
# homepage.title      = "tsummt"
# homepage.description = "tsuMomentum Scanner Dashboard"
# homepage.icon       = "📊" or "icon-chart"
# homepage.url        = "https://tsummt.milktea-jp1.feng.moe" (optional, auto-derived)
# homepage.category   = "quant" (optional, for future grouping)
# homepage.order      = "10" (optional, lower = further left)

LABEL_PREFIX = "homepage"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@dataclass
class ServiceEntry:
    name: str
    title: str
    description: str
    icon: str
    url: str
    category: str = ""
    order: int = 100
    status: str = "running"


def _extract_host_from_traefik(labels: dict) -> Optional[str]:
    """Try to extract the first Host(...) from traefik router rules."""
    for k, v in labels.items():
        if "rule" in k and "Host(" in v:
            m = re.search(r"Host\(`([^`]+)`\)", v)
            if m:
                return m.group(1)
    return None


def discover_services() -> list[ServiceEntry]:
    """Scan running Docker containers for homepage.* labels."""
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
            icon=labels.get(f"{LABEL_PREFIX}.icon", "🌐"),
            url=url,
            category=labels.get(f"{LABEL_PREFIX}.category", ""),
            order=int(labels.get(f"{LABEL_PREFIX}.order", "100")),
            status=c.status,
        ))

    services.sort(key=lambda s: (s.order, s.title))
    return services


# ── FastAPI ──────────────────────────────────────────────

app = FastAPI(title="home-portal", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/services")
def list_services():
    return [asdict(s) for s in discover_services()]


# Serve the SPA
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# Mount static assets (if any)
if os.path.isdir(os.path.join(STATIC_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
