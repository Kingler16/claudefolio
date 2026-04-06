"""
JSON-basierter Cache für Markt-, Makro- und News-Daten.
Entkoppelt die langsame Datensammlung (yfinance etc.) vom schnellen Dashboard-Laden.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "memory" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_cache(key: str, data: dict) -> None:
    """Speichert Daten im Cache mit Zeitstempel."""
    cache_entry = {
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    path = CACHE_DIR / f"{key}.json"
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(cache_entry, f, default=str, ensure_ascii=False)
        tmp_path.rename(path)
        logger.info(f"Cache geschrieben: {key}")
    except Exception as e:
        logger.error(f"Cache-Fehler beim Schreiben von {key}: {e}")
        if tmp_path.exists():
            tmp_path.unlink()


def load_cache(key: str) -> dict | None:
    """Lädt Daten aus dem Cache. Gibt None zurück wenn nicht vorhanden."""
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            entry = json.load(f)
        return entry.get("data")
    except Exception as e:
        logger.error(f"Cache-Fehler beim Laden von {key}: {e}")
        return None


def get_cache_age_minutes(key: str) -> float | None:
    """Gibt das Alter des Caches in Minuten zurück. None wenn nicht vorhanden."""
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            entry = json.load(f)
        ts = datetime.fromisoformat(entry["timestamp"])
        return (datetime.now() - ts).total_seconds() / 60
    except Exception:
        return None


def get_cache_timestamp(key: str) -> str | None:
    """Gibt den Zeitstempel des Caches als formatierten String zurück."""
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            entry = json.load(f)
        ts = datetime.fromisoformat(entry["timestamp"])
        return ts.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return None
