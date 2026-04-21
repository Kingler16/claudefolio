"""PWA-spezifische Routes: Manifest und Service Worker auf Root-Scope."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from src.config_loader import load_settings

router = APIRouter(tags=["pwa"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _public_base(request: Request) -> str:
    """Gibt die öffentliche Basis-URL zurück (ENV/Settings bevorzugt, sonst Request)."""
    configured = load_settings().get("web", {}).get("public_url")
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.get("/manifest.webmanifest", include_in_schema=False)
async def manifest(request: Request):
    base = _public_base(request)
    payload = {
        "name": "Velora",
        "short_name": "Velora",
        "description": "AI-Vermögensberater — Portfolio, Briefings, Chat.",
        "start_url": f"{base}/",
        "scope": f"{base}/",
        "display": "standalone",
        "orientation": "portrait",
        "theme_color": "#030510",
        "background_color": "#030510",
        "lang": "de",
        "dir": "ltr",
        "categories": ["finance", "productivity"],
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {
                "src": "/static/icons/icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
            {"src": "/static/icons/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
        ],
        # Share-Target wird in Phase 4 genutzt — Route existiert dann. Manifest-Eintrag
        # hier schon einzupflegen schadet nicht (Browser ignoriert fehlende Action).
        "share_target": {
            "action": "/api/share/trade",
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {
                "title": "title",
                "text": "text",
                "files": [
                    {"name": "screenshot", "accept": ["image/png", "image/jpeg", "image/webp"]}
                ],
            },
        },
    }
    return JSONResponse(payload, media_type="application/manifest+json")


@router.get("/sw.js", include_in_schema=False)
async def service_worker():
    sw_path = _STATIC_DIR / "sw.js"
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.get("/offline", response_class=HTMLResponse, include_in_schema=False)
async def offline_page():
    return FileResponse(_STATIC_DIR / "offline.html", media_type="text/html")
