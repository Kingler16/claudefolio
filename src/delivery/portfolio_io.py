"""Sichere Portfolio-IO: File-Lock + atomic write + rotating Backups.

Verhindert Race-Conditions bei parallelen Trade-Loggings (Web-UI, Telegram,
Chat) und stellt sicher, dass portfolio.json nie durch halbfertige Writes
korrumpiert wird.

Jede Mutation durchläuft `with portfolio_write_lock() as portfolio:` — Block:
1. Lock erwerben (fcntl.flock exklusiv, blockiert andere Writer).
2. Aktuelles File einlesen und zurückgeben.
3. Aufrufer mutiert das Dict.
4. Beim Verlassen: Backup (falls ≥ ~10 Min seit letztem), atomic write.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
BACKUP_DIR = Path(__file__).parent.parent.parent / "memory" / "portfolio_backups"
LOCK_FILE = CONFIG_DIR / ".portfolio.lock"
PORTFOLIO_PATH = CONFIG_DIR / "portfolio.json"

BACKUP_MIN_INTERVAL_SEC = 600  # max 1 Backup pro 10 min (sonst Spam)
BACKUP_KEEP = 60  # etwa 10 Tage bei durchschnittlich 6 Mutationen/Tag


def load_portfolio() -> dict:
    """Einfaches Laden — ohne Lock, für Read-only-Pfade."""
    with open(PORTFOLIO_PATH) as f:
        return json.load(f)


def _auto_backup() -> None:
    """Rotiert Backups: neue Kopie in memory/portfolio_backups/ wenn letztes älter als BACKUP_MIN_INTERVAL_SEC."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    existing = sorted(BACKUP_DIR.glob("portfolio_*.json"))
    if existing:
        try:
            last_ts = existing[-1].stat().st_mtime
            if now.timestamp() - last_ts < BACKUP_MIN_INTERVAL_SEC:
                return
        except OSError:
            pass
    tag = now.strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"portfolio_{tag}.json"
    try:
        shutil.copy2(PORTFOLIO_PATH, dst)
    except FileNotFoundError:
        return
    # Alte wegrotieren
    for old in existing[:-BACKUP_KEEP + 1]:
        try:
            old.unlink()
        except OSError:
            pass


def _atomic_write(portfolio: dict) -> None:
    """Schreibt portfolio.json atomar (tempfile + os.replace).
    Kein Risiko von halbfertigen Writes bei z.B. Strom-Ausfall / SIGKILL."""
    fd, tmp_path = tempfile.mkstemp(
        suffix=".json.tmp", prefix="portfolio.", dir=str(PORTFOLIO_PATH.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        # Owner + Mode der Original-Datei auf das Tempfile spiegeln, sonst
        # erbt portfolio.json nach jedem root-Write die mkstemp-Defaults
        # (root:root 0600) — und der admin-Cronjob (Briefing) verliert
        # den Lesezugriff.
        _preserve_perms(PORTFOLIO_PATH, tmp_path)
        os.replace(tmp_path, PORTFOLIO_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _preserve_perms(reference: Path, target: str | Path) -> None:
    """Spiegelt Mode (immer) und Owner (nur wenn euid=root) von `reference` auf `target`.
    Schluckt FileNotFoundError für den allerersten Write."""
    try:
        st = os.stat(reference)
    except FileNotFoundError:
        return
    try:
        os.chmod(target, st.st_mode & 0o777)
    except OSError as e:
        logger.warning("chmod auf %s fehlgeschlagen: %s", target, e)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        try:
            os.chown(target, st.st_uid, st.st_gid)
        except OSError as e:
            logger.warning("chown auf %s fehlgeschlagen: %s", target, e)


def add_new_position(ticker: str, shares: float, price_eur: float, account: str, trade_currency: str = "EUR") -> bool:
    """Legt eine komplett neue Position an + aktualisiert das Cash-Konto (atomar, mit Lock).

    `price_eur` MUSS schon in EUR sein (Caller konvertiert USD→EUR vorher).
    `trade_currency` beeinflusst nur das buy_in-Feld (Originalwährung), nicht das Cash-Tracking."""
    from datetime import datetime

    # Lokale Imports, um zirkuläre Imports zu vermeiden
    from src.delivery.telegram import update_cash_on_trade

    with portfolio_write_lock() as portfolio:
        if account not in portfolio.get("accounts", {}):
            logger.error("Konto %s existiert nicht in portfolio.json", account)
            return False

        new_pos = {
            "name": ticker,
            "isin": "",
            "ticker": ticker,
            "shares": float(shares),
            "buy_in": float(price_eur),
            "buy_in_eur": float(price_eur),
            "currency": trade_currency or "EUR",
        }
        portfolio["accounts"][account]["positions"].append(new_pos)
        try:
            update_cash_on_trade(portfolio, account, "buy", shares, price_eur)
        except Exception as e:
            logger.warning("Cash-Update fehlgeschlagen bei add_new_position: %s", e)
        portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    logger.info("Neue Position angelegt: %s %s shares=%s @ %s in %s", ticker, trade_currency, shares, price_eur, account)
    return True


@contextlib.contextmanager
def portfolio_write_lock():
    """Context-Manager: Lock, Load, (Mutate), Backup, Atomic-Save, Unlock.

    Nutzung:
        with portfolio_write_lock() as portfolio:
            portfolio["accounts"][...]["positions"].append(...)
        # Beim Verlassen: atomisch gespeichert.

    Wenn eine Exception im Block geworfen wird, wird nicht gespeichert.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Lock-File offen halten — fcntl.flock ist an Filedescriptor gebunden.
    # O_RDWR|O_CREAT statt "w": kein Truncate, damit ein als-root erstelltes
    # Lock-File später auch von admin-Prozessen (Cronjob) wieder geöffnet
    # werden kann, ohne dass jeder Aufruf Owner/Mode überschreibt.
    fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o664)
    with os.fdopen(fd, "r+") as lockfile:
        try:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
        except OSError as e:
            logger.warning("Portfolio-Lock konnte nicht erworben werden: %s — trotzdem weitermachen", e)

        try:
            with open(PORTFOLIO_PATH) as f:
                portfolio = json.load(f)
        except Exception as e:
            logger.error("portfolio.json konnte nicht geladen werden: %s", e)
            raise

        try:
            yield portfolio
            _auto_backup()
            _atomic_write(portfolio)
        finally:
            try:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
