"""
Performance-Tracking: Benchmark-Vergleich, Recommendation-Tracking, Tax-Loss-Harvesting.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"


def compute_benchmark_data(market_data: dict) -> list:
    """Berechnet Benchmark-Daten als strukturierte Liste."""
    indices = market_data.get("indices", {})
    benchmarks = []

    for name in ["S&P 500", "NASDAQ", "DAX", "ATX", "Euro Stoxx 50", "Gold", "BTC/USD"]:
        if name in indices:
            change = indices[name].get("change_pct", 0)
            benchmarks.append({"name": name, "change_pct": change})

    benchmarks.sort(key=lambda x: x["change_pct"], reverse=True)
    return benchmarks


def calculate_benchmark_comparison(market_data: dict) -> str:
    """Vergleicht Portfolio-Performance mit Benchmarks."""
    benchmarks = compute_benchmark_data(market_data)

    if not benchmarks:
        return "Keine Benchmark-Daten verfügbar."

    lines = ["BENCHMARK-VERGLEICH (Wochenperformance):"]
    for b in benchmarks:
        change = b["change_pct"]
        bar = "+" * int(abs(change)) if change > 0 else "-" * int(abs(change))
        lines.append(f"  {b['name']:20s}: {change:+.2f}% {bar}")

    return "\n".join(lines)


def _load_tax_rate() -> float:
    """Lädt Steuersatz aus Settings."""
    try:
        settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)
        return settings.get("user", {}).get("tax_rate", 0.275)
    except Exception:
        return 0.275


def compute_tax_loss_data(portfolio: dict, market_data: dict, tax_rate: float = None) -> dict:
    """Berechnet Tax-Loss-Harvesting Daten als strukturiertes Dict."""
    if tax_rate is None:
        tax_rate = _load_tax_rate()

    gains = []
    losses = []

    indices = market_data.get("indices", {})
    eur_usd = indices.get("EUR/USD", {}).get("value", 1.0)

    for account_name, account in portfolio.get("accounts", {}).items():
        for pos in account.get("positions", []):
            ticker = pos.get("ticker")
            if not ticker or ticker not in market_data.get("positions", {}):
                continue

            shares = pos["shares"]
            buy_in = pos["buy_in"]
            currency = pos.get("currency", "EUR")
            current_price = market_data["positions"][ticker].get("price", {}).get("current_price")

            if not current_price:
                continue

            if currency == "USD":
                buy_in_eur = buy_in / eur_usd
                current_eur = current_price / eur_usd
            else:
                buy_in_eur = buy_in
                current_eur = current_price

            pnl_eur = (current_eur - buy_in_eur) * shares
            pnl_pct = ((current_eur / buy_in_eur) - 1) * 100 if buy_in_eur else 0

            entry = {
                "name": pos["name"],
                "ticker": ticker,
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 1),
                "account": account_name,
            }

            if pnl_eur > 0:
                gains.append(entry)
            elif pnl_eur < 0:
                losses.append(entry)

    total_gains = sum(g["pnl_eur"] for g in gains)
    total_losses = sum(l["pnl_eur"] for l in losses)
    potential_tax = total_gains * tax_rate
    net_after_harvesting = (total_gains + total_losses) * tax_rate
    tax_savings = potential_tax - max(0, net_after_harvesting)

    return {
        "tax_rate": tax_rate,
        "total_gains": round(total_gains, 2),
        "total_losses": round(total_losses, 2),
        "potential_tax": round(potential_tax, 2),
        "net_tax": round(max(0, net_after_harvesting), 2),
        "tax_savings": round(tax_savings, 2),
        "gains": sorted(gains, key=lambda x: x["pnl_eur"], reverse=True),
        "losses": sorted(losses, key=lambda x: x["pnl_eur"]),
    }


def find_tax_loss_harvesting(portfolio: dict, market_data: dict, tax_rate: float = None) -> str:
    """Identifiziert Tax-Loss-Harvesting Opportunitäten (String-Format für Prompts)."""
    data = compute_tax_loss_data(portfolio, market_data, tax_rate)

    lines = [
        "TAX-LOSS-HARVESTING ANALYSE (KESt 27.5%):",
        f"  Unrealisierte Gewinne: {data['total_gains']:+.2f}€",
        f"  Unrealisierte Verluste: {data['total_losses']:+.2f}€",
        f"  Potenzielle KESt auf Gewinne: {data['potential_tax']:.2f}€",
        f"  KESt nach Verlustverrechnung: {data['net_tax']:.2f}€",
        f"  Mögliche Steuerersparnis: {data['tax_savings']:.2f}€",
        "",
        "  Verlust-Positionen (Kandidaten für Harvesting):",
    ]
    for l in data["losses"]:
        lines.append(f"    {l['name']} ({l['ticker']}): {l['pnl_eur']:+.2f}€ ({l['pnl_pct']:+.1f}%) [{l['account']}]")

    lines.append("")
    lines.append("  Gewinn-Positionen:")
    for g in data["gains"]:
        lines.append(f"    {g['name']} ({g['ticker']}): {g['pnl_eur']:+.2f}€ ({g['pnl_pct']:+.1f}%) [{g['account']}]")

    return "\n".join(lines)


def compute_recommendation_data(market_data: dict) -> dict:
    """Berechnet Empfehlungs-Performance als strukturiertes Dict."""
    recs_path = MEMORY_DIR / "recommendations.json"
    if not recs_path.exists():
        return {"open": [], "wins": [], "losses": [], "hit_rate": 0, "total_closed": 0}

    with open(recs_path) as f:
        recs = json.load(f)

    if not recs:
        return {"open": [], "wins": [], "losses": [], "hit_rate": 0, "total_closed": 0}

    open_recs = []
    wins = []
    losses = []

    for rec in recs:
        status = rec.get("status", "open")
        if status == "open":
            open_recs.append(rec)
        elif status == "target_hit":
            wins.append(rec)
        elif status == "stop_hit":
            losses.append(rec)

    total_closed = len(wins) + len(losses)
    hit_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0

    return {
        "open": open_recs,
        "wins": wins,
        "losses": losses,
        "hit_rate": round(hit_rate, 0),
        "total_closed": total_closed,
        "open_count": len(open_recs),
    }


def track_recommendation_performance(market_data: dict) -> str:
    """Trackt wie vergangene Empfehlungen performt haben (String-Format für Prompts)."""
    data = compute_recommendation_data(market_data)

    if not data["open"] and not data["wins"] and not data["losses"]:
        return "Noch keine Empfehlungen zum Tracken."

    lines = ["EMPFEHLUNGS-BILANZ:"]
    lines.append(f"  Abgeschlossen: {data['total_closed']} (Hit-Rate: {data['hit_rate']:.0f}%) | Offen: {data['open_count']}")

    for rec in data["open"]:
        ticker = rec.get("ticker", "?")
        action = rec.get("action", "?")
        date = rec.get("date", "?")[:10]
        unrealized = rec.get("unrealized_pct")
        if unrealized is not None:
            emoji = "\U0001f4c8" if unrealized > 0 else "\U0001f4c9"
            lines.append(f"  {emoji} OFFEN {date}: {action} {ticker} \u2192 {unrealized:+.1f}%")

    for rec in data["wins"]:
        lines.append(f"  \u2705 {rec.get('date', '?')[:10]}: {rec.get('action', '?')} {rec.get('ticker', '?')} \u2192 Ziel erreicht")

    for rec in data["losses"]:
        lines.append(f"  \u274c {rec.get('date', '?')[:10]}: {rec.get('action', '?')} {rec.get('ticker', '?')} \u2192 Stop ausgelöst")

    return "\n".join(lines)
