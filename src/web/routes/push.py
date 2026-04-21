"""Push-Notification-API: Subscribe/Unsubscribe/Preferences/Test."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.chat.db import (
    deactivate_push_subscription,
    get_notification_preferences,
    set_notification_preference,
    upsert_push_subscription,
)
from src.config_loader import load_settings
from src.delivery.push_sender import send_push

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/vapid-public-key")
async def vapid_public_key():
    key = load_settings().get("web_push", {}).get("vapid_public_key") or ""
    return {"key": key, "configured": bool(key)}


@router.post("/subscribe")
async def subscribe(req: Request):
    data = await req.json()
    sub = data.get("subscription") or data
    endpoint = sub.get("endpoint")
    keys = sub.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not (endpoint and p256dh and auth):
        raise HTTPException(status_code=400, detail="Invalid subscription payload")
    upsert_push_subscription(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=req.headers.get("user-agent", "")[:200],
    )
    logger.info("Push-Subscription registriert: %s…", endpoint[:60])
    return {"status": "ok"}


@router.post("/unsubscribe")
async def unsubscribe(req: Request):
    data = await req.json()
    endpoint = data.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint required")
    deactivate_push_subscription(endpoint)
    return {"status": "ok"}


@router.get("/preferences")
async def get_preferences():
    return get_notification_preferences()


@router.post("/preferences")
async def set_preferences(req: Request):
    """Body: { category: { telegram_enabled, push_enabled } } — bulk update."""
    body = await req.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="expected object")
    updated = 0
    for category, prefs in body.items():
        if not isinstance(prefs, dict):
            continue
        set_notification_preference(
            category=category,
            telegram_enabled=bool(prefs.get("telegram_enabled", True)),
            push_enabled=bool(prefs.get("push_enabled", True)),
        )
        updated += 1
    return {"status": "ok", "updated": updated}


@router.post("/test")
async def test_push():
    """Schickt eine Test-Push an alle aktiven Subscriptions (ignoriert Kategorien-Toggle)."""
    # Direkt ohne Kategorien-Filter senden — test ist immer gewollt
    count = send_push(
        category="test",
        title="Velora-Push funktioniert ✓",
        body="Dies ist eine Test-Benachrichtigung.",
        url="/",
        tag="velora-test",
    )
    return JSONResponse({"status": "ok", "sent": count})
