"""
Claude Code CLI Wrapper.
Ruft Claude im non-interactive Modus auf.
"""

import json
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def ask_claude(system_prompt: str, user_prompt: str, timeout: int = 1200) -> dict:
    """
    Ruft Claude Code CLI auf und gibt Analyse + strukturierte Daten zurück.
    Prompt wird via stdin übergeben (keine Längenlimitierung).
    """
    # Claude CLI finden: Settings > shutil.which > bekannte Pfade > fallback
    import shutil
    claude_bin = "claude"
    try:
        settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)
        claude_bin = settings.get("claude", {}).get("command", "claude")
    except Exception:
        pass
    if claude_bin == "claude":
        found = shutil.which("claude")
        if found:
            claude_bin = found
        elif Path("/usr/local/bin/claude").exists():
            claude_bin = "/usr/local/bin/claude"

    cmd = [
        claude_bin,
        "--print",
        "--system-prompt", system_prompt,
        "--tools", "",
        "--no-session-persistence",
        "--model", "opus",
        "--effort", "high",
    ]

    try:
        logger.info(f"Claude CLI wird aufgerufen (Prompt: {len(user_prompt)} Zeichen)...")
        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            logger.error(f"Claude CLI Fehler (exit {result.returncode}): {result.stderr[:500]}")
            return {"text": f"Fehler: {result.stderr[:500]}", "structured": None}

        output = result.stdout.strip()
        if not output:
            logger.error(f"Claude CLI leere Ausgabe. Stderr: {result.stderr[:500]}")
            return {"text": "Fehler: Leere Antwort von Claude", "structured": None}

        logger.info(f"Claude Antwort: {len(output)} Zeichen")
        structured = extract_json_block(output)

        return {
            "text": output,
            "structured": structured,
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Claude CLI Timeout nach {timeout}s")
        return {"text": "Fehler: Timeout", "structured": None}
    except FileNotFoundError:
        logger.error("Claude CLI nicht gefunden. Ist 'claude' im PATH?")
        return {"text": "Fehler: Claude CLI nicht installiert", "structured": None}


def extract_json_block(text: str) -> dict | None:
    """Extrahiert den JSON-Block aus Claudes Antwort."""
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError as e:
            logger.error(f"JSON-Parse-Fehler: {e}")
    return None


def strip_json_block(text: str) -> str:
    """Entfernt den JSON-Block aus dem Text (für Telegram)."""
    pattern = r"\n*```json\s*\n.*?\n\s*```\s*$"
    return re.sub(pattern, "", text, flags=re.DOTALL).strip()
