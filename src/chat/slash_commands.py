"""Slash-Command-Router für den Web-Chat.

Fängt Eingaben ab, die mit `/` beginnen, bevor sie an die Claude CLI gehen —
die CLI würde sie sonst als eigene Slash-Commands interpretieren und mit
"Unknown command" antworten.

Handler yielden dieselben StreamEvents wie `stream_chat`, sodass die Route
beide Quellen einheitlich dispatchen kann.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable

from src.chat.claude_stream import StreamEvent

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


def is_slash_command(message: str) -> bool:
    stripped = message.lstrip()
    return stripped.startswith("/")


def _parse(message: str) -> tuple[str, str]:
    stripped = message.strip().lstrip("/")
    parts = stripped.split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1].strip() if len(parts) > 1 else ""
    return cmd, args


async def handle_slash(message: str) -> AsyncIterator[StreamEvent]:
    cmd, args = _parse(message)
    handler = HANDLERS.get(cmd)
    try:
        if handler:
            async for ev in handler(args):
                yield ev
        else:
            yield StreamEvent(
                "assistant_message",
                {"text": f"Unbekannter Command `/{cmd}`. Tippe `/help` für eine Übersicht."},
            )
    except Exception as e:
        logger.exception("Slash-Command /%s failed", cmd)
        yield StreamEvent("error", {"message": f"/{cmd} fehlgeschlagen: {e}"})

    yield StreamEvent("done", {
        "session_id": None,
        "total_cost_usd": 0,
        "num_turns": 0,
        "is_error": False,
    })


# ── Handler ──────────────────────────────────────────────────────────

async def _help(_: str) -> AsyncIterator[StreamEvent]:
    text = (
        "**Verfügbare Commands**\n\n"
        "- `/briefing` — die letzten 5 Briefings auflisten\n"
        "- `/briefing YYYY-MM-DD` — Volltext eines bestimmten Briefings\n"
        "- `/briefing new` — neues Briefing generieren (läuft ~2–3 Min im Hintergrund, Ergebnis landet auf /briefings und Telegram)\n"
        "- `/status` — Portfolio-Übersicht\n"
        "- `/help` — diese Hilfe\n\n"
        "Für alles andere einfach schreiben — ich antworte als dein Berater."
    )
    yield StreamEvent("assistant_message", {"text": text})


async def _briefing(args: str) -> AsyncIterator[StreamEvent]:
    arg = args.strip()
    arg_lower = arg.lower()

    if arg_lower in ("new", "neu", "generate"):
        _spawn_briefing_subprocess()
        yield StreamEvent(
            "assistant_message",
            {"text": (
                "📊 **Briefing wird generiert…**\n\n"
                "Das dauert ca. 2–3 Minuten. Das Ergebnis erscheint auf der "
                "[Briefings-Seite](/briefings) und wird per Telegram gesendet."
            )},
        )
        return

    briefings_path = MEMORY_DIR / "briefings.json"
    if not briefings_path.exists():
        yield StreamEvent(
            "assistant_message",
            {"text": "_Noch keine Briefings vorhanden._ Starte eins mit `/briefing new`."},
        )
        return

    try:
        with open(briefings_path) as f:
            data = json.load(f)
    except Exception as e:
        yield StreamEvent("error", {"message": f"Briefings konnten nicht geladen werden: {e}"})
        return

    briefings = sorted(data or [], key=lambda b: b.get("date", ""), reverse=True)

    if arg and arg[0].isdigit():
        match = next((b for b in briefings if (b.get("date") or "").startswith(arg)), None)
        if not match:
            yield StreamEvent(
                "assistant_message",
                {"text": f"Kein Briefing mit Datum `{arg}` gefunden."},
            )
            return
        full = match.get("full_text") or match.get("summary") or "_leer_"
        yield StreamEvent(
            "assistant_message",
            {"text": f"### Briefing {match.get('date')}\n\n{full}"},
        )
        return

    if not briefings:
        yield StreamEvent(
            "assistant_message",
            {"text": "_Noch keine Briefings vorhanden._ Starte eins mit `/briefing new`."},
        )
        return

    lines = ["### Letzte Briefings", ""]
    for b in briefings[:5]:
        date = b.get("date", "?")
        regime = b.get("market_regime")
        summary = (b.get("summary") or "").strip()
        header = f"**{date}**"
        if regime:
            header += f" · _{regime}_"
        lines.append(header)
        if summary:
            lines.append(summary)
        lines.append("")
    lines.append("_Volltext: `/briefing YYYY-MM-DD` · Neu generieren: `/briefing new`_")
    yield StreamEvent("assistant_message", {"text": "\n".join(lines)})


async def _status(_: str) -> AsyncIterator[StreamEvent]:
    pf_path = CONFIG_DIR / "portfolio.json"
    if not pf_path.exists():
        yield StreamEvent("assistant_message", {"text": "_Kein Portfolio konfiguriert._"})
        return
    with open(pf_path) as f:
        portfolio = json.load(f)

    lines = [f"### Portfolio (Stand: {portfolio.get('last_updated', '?')})", ""]
    for acc_name, acc in portfolio.get("accounts", {}).items():
        positions = acc.get("positions", [])
        lines.append(f"**{acc_name}** — {len(positions)} Positionen")
        for pos in positions:
            name = pos.get("name", "?")
            shares = pos.get("shares", 0) or 0
            lines.append(f"- {name}: {shares:.2f} Stk")
        lines.append("")
    for name, bank_acc in portfolio.get("bank_accounts", {}).items():
        depot = " _(depot)_" if bank_acc.get("is_depot_cash") else ""
        value = bank_acc.get("value", 0) or 0
        lines.append(f"💰 **{name}**: {value:.2f}€{depot}")
    yield StreamEvent("assistant_message", {"text": "\n".join(lines)})


def _spawn_briefing_subprocess():
    """Startet `python -m src.main briefing` als eigenständigen Subprocess.

    Der laufende FastAPI-Prozess darf nicht blockieren — run_briefing ruft
    intern synchrone subprocess-/HTTP-Calls, die den Event-Loop anhalten.
    """
    import subprocess
    import sys
    project_root = Path(__file__).parent.parent.parent
    try:
        subprocess.Popen(
            [sys.executable, "-m", "src.main", "briefing"],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        logger.exception("Failed to spawn briefing subprocess")


HANDLERS: dict[str, Callable[[str], AsyncIterator[StreamEvent]]] = {
    "help": _help,
    "briefing": _briefing,
    "status": _status,
}
