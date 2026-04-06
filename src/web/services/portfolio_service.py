"""
Portfolio-Service: Berechnet strukturierte Portfolio-Daten für das Web-Dashboard.
Logik extrahiert aus prompt.py:build_portfolio_summary(), aber als Dicts statt Strings.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"

# Display-Namen für Konten
ACCOUNT_DISPLAY_NAMES = {
    "trade_republic": "Trade Republic",
    "erste_bank": "Erste Bank",
    "interactive_brokers": "Interactive Brokers",
    "flatex": "Flatex",
    "scalable": "Scalable Capital",
}

# Index-Beschreibungen für die Markt-Seite
INDEX_DESCRIPTIONS = {
    "S&P 500": "US Large Cap",
    "NASDAQ": "US Tech",
    "DAX": "Deutschland 40",
    "ATX": "Österreich",
    "Euro Stoxx 50": "Europa Top 50",
    "Gold": "Edelmetall (XAU)",
    "BTC/USD": "Bitcoin",
    "EUR/USD": "Wechselkurs",
    "VIX": "Volatilitätsindex",
}


def load_portfolio() -> dict:
    """Lädt Portfolio aus config/portfolio.json."""
    path = CONFIG_DIR / "portfolio.json"
    if not path.exists():
        return {"accounts": {}, "bank_accounts": {}, "user_profile": {}}
    with open(path) as f:
        return json.load(f)


def load_watchlist() -> list:
    """Lädt Watchlist."""
    path = CONFIG_DIR / "watchlist.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def compute_portfolio_overview(portfolio: dict, market_data: dict) -> dict:
    """
    Berechnet vollständige Portfolio-Übersicht als strukturiertes Dict.
    Gibt zurück: total_value, holdings_value, cash, pnl, positions[], bank_accounts[], etc.
    """
    positions = []
    total_value_eur = 0
    total_invested_eur = 0

    # EUR/USD Kurs
    indices = market_data.get("indices", {})
    eur_usd = 1.0
    if "EUR/USD" in indices:
        eur_usd = indices["EUR/USD"].get("value", 1.0) or 1.0

    for account_name, account in portfolio.get("accounts", {}).items():
        for pos in account.get("positions", []):
            ticker = pos.get("ticker")
            shares = pos.get("shares", 0)
            buy_in = pos.get("buy_in", 0)
            currency = pos.get("currency", "EUR")
            name = pos.get("name", ticker or "Unbekannt")
            isin = pos.get("isin", "")

            # Buy-In in EUR
            buy_in_eur = buy_in if currency == "EUR" else buy_in / eur_usd
            invested_eur = shares * buy_in_eur

            current_price = None
            price_data = {}
            if ticker and ticker in market_data.get("positions", {}):
                price_data = market_data["positions"][ticker].get("price", {})
                current_price = price_data.get("current_price")

            has_live_price = current_price is not None
            if has_live_price:
                current_price_eur = current_price if currency == "EUR" else current_price / eur_usd
                current_value_eur = shares * current_price_eur
                pnl_eur = current_value_eur - invested_eur
                pnl_pct = (pnl_eur / invested_eur * 100) if invested_eur else 0
            else:
                current_price_eur = buy_in_eur
                current_value_eur = invested_eur
                pnl_eur = 0
                pnl_pct = 0

            total_value_eur += current_value_eur
            total_invested_eur += invested_eur

            positions.append({
                "name": name,
                "ticker": ticker or "",
                "isin": isin,
                "account": account_name,
                "shares": shares,
                "buy_in": buy_in,
                "buy_in_eur": round(buy_in_eur, 2),
                "currency": currency,
                "current_price": current_price,
                "current_price_eur": round(current_price_eur, 2),
                "current_value_eur": round(current_value_eur, 2),
                "invested_eur": round(invested_eur, 2),
                "pnl_eur": round(pnl_eur, 2),
                "pnl_pct": round(pnl_pct, 1),
                "has_live_price": has_live_price,
                "sector": price_data.get("sector", ""),
                "beta": price_data.get("beta"),
                "pe_ratio": price_data.get("pe_ratio"),
                "dividend_yield": price_data.get("dividend_yield"),
                "change_pct": price_data.get("change_pct"),
                "perf_1m_pct": price_data.get("perf_1m_pct"),
                "perf_6m_pct": price_data.get("perf_6m_pct"),
                "perf_1y_pct": price_data.get("perf_1y_pct"),
                "high_52w": price_data.get("52w_high"),
                "low_52w": price_data.get("52w_low"),
            })

    # Allocation berechnen
    holdings_value = total_value_eur  # vor Cash
    for p in positions:
        p["allocation_pct"] = round(p["current_value_eur"] / holdings_value * 100, 1) if holdings_value else 0

    # Bankkonten
    bank_accounts = []
    cash_total = 0
    depot_cash = 0
    free_cash = 0
    for name, acc in portfolio.get("bank_accounts", {}).items():
        val = acc.get("value", 0)
        is_depot = acc.get("is_depot_cash", False)
        cash_total += val
        if is_depot:
            depot_cash += val
        else:
            free_cash += val
        bank_accounts.append({
            "name": name,
            "bank": acc.get("bank", ""),
            "value": val,
            "interest": acc.get("interest", 0),
            "note": acc.get("note", ""),
            "is_depot_cash": is_depot,
        })

    total_value_eur += cash_total
    total_pnl_eur = total_value_eur - total_invested_eur - cash_total
    total_pnl_pct = (total_pnl_eur / total_invested_eur * 100) if total_invested_eur else 0

    # Sortiere Positionen nach Wert (absteigend)
    positions.sort(key=lambda p: p["current_value_eur"], reverse=True)

    # Währungs-Exposure
    usd_positions = [p for p in positions if p["currency"] == "USD"]
    eur_positions = [p for p in positions if p["currency"] != "USD"]
    usd_value = sum(p["current_value_eur"] for p in usd_positions)
    eur_value = sum(p["current_value_eur"] for p in eur_positions)

    # Sektor-Breakdown
    sectors = {}
    for p in positions:
        sector = p["sector"] or "Unbekannt"
        sectors[sector] = sectors.get(sector, 0) + p["current_value_eur"]

    # Account-Breakdown
    accounts = {}
    for p in positions:
        acc = p["account"]
        accounts[acc] = accounts.get(acc, 0) + p["current_value_eur"]

    # Account-gruppierte Positionen mit Display-Namen
    accounts_grouped = {}
    for p in positions:
        acc = p["account"]
        if acc not in accounts_grouped:
            accounts_grouped[acc] = {
                "display_name": ACCOUNT_DISPLAY_NAMES.get(acc, acc.replace("_", " ").title()),
                "positions": [],
                "total_value": 0,
                "total_pnl": 0,
            }
        accounts_grouped[acc]["positions"].append(p)
        accounts_grouped[acc]["total_value"] += p["current_value_eur"]
        accounts_grouped[acc]["total_pnl"] += p["pnl_eur"]
    for acc in accounts_grouped.values():
        acc["total_value"] = round(acc["total_value"], 2)
        acc["total_pnl"] = round(acc["total_pnl"], 2)

    return {
        "total_value_eur": round(total_value_eur, 2),
        "holdings_value_eur": round(holdings_value, 2),
        "cash_total": round(cash_total, 2),
        "depot_cash": round(depot_cash, 2),
        "free_cash": round(free_cash, 2),
        "total_invested_eur": round(total_invested_eur, 2),
        "total_pnl_eur": round(total_pnl_eur, 2),
        "total_pnl_pct": round(total_pnl_pct, 1),
        "position_count": len(positions),
        "positions": positions,
        "bank_accounts": bank_accounts,
        "eur_usd_rate": eur_usd,
        "currency_exposure": {
            "EUR": round(eur_value, 2),
            "USD": round(usd_value, 2),
        },
        "sector_breakdown": {k: round(v, 2) for k, v in sorted(sectors.items(), key=lambda x: x[1], reverse=True)},
        "account_breakdown": {k: round(v, 2) for k, v in sorted(accounts.items(), key=lambda x: x[1], reverse=True)},
        "accounts_grouped": accounts_grouped,
    }


def compute_index_data(market_data: dict) -> list:
    """Extrahiert Index-Daten als Liste für die Anzeige."""
    indices = market_data.get("indices", {})
    result = []
    for name in ["S&P 500", "NASDAQ", "DAX", "ATX", "Euro Stoxx 50", "Gold", "BTC/USD", "EUR/USD", "VIX"]:
        if name in indices:
            idx = indices[name]
            result.append({
                "name": name,
                "description": INDEX_DESCRIPTIONS.get(name, ""),
                "value": idx.get("value"),
                "change_pct": idx.get("change_pct"),
            })
    return result
