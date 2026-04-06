"""
FastAPI Web-Dashboard für claudefolio.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.web.i18n import get_translations
from src.web.services.portfolio_service import (
    load_portfolio,
    load_watchlist,
    compute_portfolio_overview,
    compute_index_data,
)
from src.web.services.cache_service import (
    get_market_data,
    get_macro_data,
    get_news_data,
    get_calendar_data,
    get_cache_status,
    get_monthly_snapshots,
    get_briefings,
    get_recommendations,
    get_notes,
)
from src.analysis.performance import compute_benchmark_data, compute_tax_loss_data, compute_recommendation_data
from src.data.cache import save_cache

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Background refresh state
_refresh_running = False
_refresh_lock = asyncio.Lock()


def format_eur(value):
    """Jinja2 Filter: Zahl als EUR formatieren."""
    if value is None:
        return "–"
    return f"{value:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")


def format_pct(value):
    """Jinja2 Filter: Zahl als Prozent formatieren."""
    if value is None or not isinstance(value, (int, float)):
        return "–"
    return f"{value:+.1f}%"


def format_number(value, decimals=2):
    """Jinja2 Filter: Zahl formatieren."""
    if value is None:
        return "–"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("claudefolio Dashboard gestartet")
    from src.data.cache import get_cache_age_minutes
    age = get_cache_age_minutes("market_data")
    if age is None:
        logger.info("Kein Cache vorhanden — starte automatischen Daten-Refresh...")
        asyncio.create_task(_run_refresh())
    else:
        logger.info(f"Cache gefunden (Alter: {age:.0f} Minuten)")
    yield
    logger.info("claudefolio Dashboard gestoppt")


app = FastAPI(title="claudefolio Dashboard", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Jinja2 custom filters
templates.env.filters["eur"] = format_eur
templates.env.filters["pct"] = format_pct
templates.env.filters["number"] = format_number


def _get_lang() -> str:
    """Liest die Sprache aus settings.json."""
    try:
        import json as _json
        settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        with open(settings_path) as f:
            return _json.load(f).get("user", {}).get("language", "de")
    except Exception:
        return "de"


def _ctx(request, page: str, **extra) -> dict:
    """Baut den Template-Kontext mit Übersetzungen."""
    lang = _get_lang()
    t = get_translations(lang)
    return {"request": request, "page": page, "t": t, "lang": lang, **extra}


# ─── HTML Pages ──────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    portfolio = load_portfolio()
    market_data = get_market_data()
    overview = compute_portfolio_overview(portfolio, market_data)
    indices = compute_index_data(market_data)
    snapshots = get_monthly_snapshots()
    cache_status = get_cache_status()

    return templates.TemplateResponse(request, "dashboard.html", _ctx(request, "dashboard",
        overview=overview, indices=indices, snapshots=snapshots, cache_status=cache_status,
    ))


@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    portfolio = load_portfolio()
    market_data = get_market_data()
    overview = compute_portfolio_overview(portfolio, market_data)
    cache_status = get_cache_status()

    return templates.TemplateResponse(request, "portfolio.html", _ctx(request, "portfolio",
        overview=overview, portfolio_raw=portfolio, cache_status=cache_status,
    ))


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    portfolio = load_portfolio()
    market_data = get_market_data()
    overview = compute_portfolio_overview(portfolio, market_data)
    snapshots = get_monthly_snapshots()
    cache_status = get_cache_status()
    benchmarks = compute_benchmark_data(market_data)
    tax_loss = compute_tax_loss_data(portfolio, market_data) if market_data.get("positions") else None

    return templates.TemplateResponse(request, "analysis.html", _ctx(request, "analysis",
        overview=overview, snapshots=snapshots, cache_status=cache_status, benchmarks=benchmarks, tax_loss=tax_loss,
    ))


@app.get("/market", response_class=HTMLResponse)
async def market_page(request: Request):
    market_data = get_market_data()
    macro_data = get_macro_data()
    calendar_data = get_calendar_data()
    indices = compute_index_data(market_data)
    cache_status = get_cache_status()

    return templates.TemplateResponse(request, "market.html", _ctx(request, "market",
        indices=indices, macro=macro_data, calendar=calendar_data, cache_status=cache_status,
    ))


@app.get("/briefings", response_class=HTMLResponse)
async def briefings_page(request: Request):
    return templates.TemplateResponse(request, "briefings.html", _ctx(request, "briefings",
        briefings=get_briefings(), notes=get_notes(),
    ))


@app.get("/recommendations", response_class=HTMLResponse)
async def recommendations_page(request: Request):
    return templates.TemplateResponse(request, "recommendations.html", _ctx(request, "recommendations",
        recommendations=get_recommendations(), notes=get_notes(),
    ))


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    import json as _json
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    with open(settings_path) as f:
        settings = _json.load(f)
    portfolio = load_portfolio()

    return templates.TemplateResponse(request, "settings.html", _ctx(request, "settings",
        settings=settings, accounts=list(portfolio.get("accounts", {}).keys()), portfolio=portfolio,
    ))


# ─── HTMX Partials ───────────────────────────────────────────

@app.get("/api/partial/indices", response_class=HTMLResponse)
async def partial_indices():
    """HTMX partial: Index-Leiste HTML."""
    market_data = get_market_data()
    indices = compute_index_data(market_data)
    if not indices:
        return '<div class="index-bar" style="color:var(--text-muted);font-size:13px;">Keine Index-Daten</div>'

    html = '<div class="index-bar">'
    for idx in indices:
        val = idx.get("value")
        change = idx.get("change_pct")
        val_str = f"{val:,.4f}" if idx["name"] == "EUR/USD" and val else (f"{val:,.0f}" if val else "–")
        change_cls = "positive" if change and change >= 0 else "negative" if change else ""
        change_str = f"{change:+.1f}%" if change is not None else ""
        html += f'''<div class="index-item">
            <span class="index-name">{idx["name"]}</span>
            <span class="index-value">{val_str}</span>
            <span class="index-change {change_cls}">{change_str}</span>
        </div>'''
    html += '</div>'
    return html


@app.get("/api/partial/cache-status", response_class=HTMLResponse)
async def partial_cache_status():
    """HTMX partial: Cache-Status als HTML für die Sidebar."""
    status = get_cache_status()
    market = status.get("market_data", {})

    if _refresh_running:
        return '<span class="cache-dot stale"></span> Daten werden geladen...'

    if market.get("available"):
        age = market.get("age_minutes", 0)
        ts = market.get("timestamp", "")
        if age < 60:
            dot = "fresh"
            label = f"Aktuell ({ts})"
        elif age < 360:
            dot = "stale"
            label = f"{int(age)}min alt ({ts})"
        else:
            dot = "stale"
            label = f"{int(age / 60)}h alt ({ts})"
        return f'<span class="cache-dot {dot}"></span> {label}'
    else:
        return '<span class="cache-dot missing"></span> Keine Daten — klicke Aktualisieren'


# ─── JSON API ────────────────────────────────────────────────

@app.get("/api/portfolio/summary")
async def api_portfolio_summary():
    portfolio = load_portfolio()
    market_data = get_market_data()
    overview = compute_portfolio_overview(portfolio, market_data)
    return JSONResponse(overview)


@app.get("/api/portfolio/history")
async def api_portfolio_history():
    return JSONResponse(get_monthly_snapshots())


@app.get("/api/market/indices")
async def api_market_indices():
    market_data = get_market_data()
    return JSONResponse(compute_index_data(market_data))


@app.get("/api/market/macro")
async def api_market_macro():
    return JSONResponse(get_macro_data())


@app.get("/api/briefings")
async def api_briefings():
    return JSONResponse(get_briefings())


@app.get("/api/recommendations")
async def api_recommendations():
    return JSONResponse(get_recommendations())


@app.get("/api/calendar")
async def api_calendar():
    return JSONResponse(get_calendar_data())


@app.get("/api/cache/status")
async def api_cache_status():
    return JSONResponse(get_cache_status())


# ─── Trade Logging ───────────────────────────────────────────

@app.post("/api/trade")
async def api_log_trade(request: Request):
    """Loggt einen Kauf oder Verkauf."""
    import json as _json
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Ungültiger JSON-Body"}, status_code=400)

    action = body.get("action")
    ticker = body.get("ticker", "").strip().upper()
    account = body.get("account", "")

    try:
        shares = float(body.get("shares", 0))
        price = float(body.get("price", 0))
    except (ValueError, TypeError):
        return JSONResponse({"error": "shares und price müssen Zahlen sein"}, status_code=400)

    if action not in ("buy", "sell"):
        return JSONResponse({"error": "action muss 'buy' oder 'sell' sein"}, status_code=400)
    if not ticker:
        return JSONResponse({"error": "Ticker fehlt"}, status_code=400)
    if shares <= 0 or price <= 0:
        return JSONResponse({"error": "shares und price müssen > 0 sein"}, status_code=400)

    from src.delivery.telegram import update_portfolio_position, close_recommendation_on_trade

    portfolio = load_portfolio()
    if account not in portfolio.get("accounts", {}):
        return JSONResponse({"error": f"Account '{account}' nicht gefunden"}, status_code=404)

    success = update_portfolio_position(action, ticker, shares, price)
    if success:
        close_recommendation_on_trade(ticker, action)
        return JSONResponse({"status": "ok", "message": f"{shares}x {ticker} {'gekauft' if action == 'buy' else 'verkauft'} @ {price}"})
    else:
        # Position nicht gefunden — bei Kauf neue Position anlegen
        if action == "buy":
            portfolio = load_portfolio()
            if account in portfolio["accounts"]:
                currency = "USD" if not any(c in ticker for c in [".", "AT0"]) else "EUR"
                portfolio["accounts"][account]["positions"].append({
                    "name": ticker,
                    "isin": "",
                    "ticker": ticker,
                    "shares": shares,
                    "buy_in": price,
                    "currency": currency,
                })
                from datetime import datetime
                portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                config_path = Path(__file__).parent.parent.parent / "config" / "portfolio.json"
                with open(config_path, "w") as f:
                    _json.dump(portfolio, f, indent=2, ensure_ascii=False)
                close_recommendation_on_trade(ticker, action)
                return JSONResponse({"status": "ok", "message": f"Neue Position: {shares}x {ticker} @ {price} in {account}"})

        return JSONResponse({"error": f"Ticker {ticker} nicht gefunden in {account}"}, status_code=404)


@app.get("/api/accounts")
async def api_accounts():
    """Gibt verfügbare Accounts zurück."""
    portfolio = load_portfolio()
    accounts = list(portfolio.get("accounts", {}).keys())
    return JSONResponse(accounts)


# ─── Recommendation Management ───────────────────────────────

@app.post("/api/recommendations/close")
async def api_close_recommendation(request: Request):
    """Schließt eine Empfehlung als ausgeführt."""
    import json as _json
    body = await request.json()
    ticker = body.get("ticker", "").strip()
    status = body.get("status", "executed")  # executed, target_hit, stop_hit, cancelled

    if not ticker:
        return JSONResponse({"error": "Ticker fehlt"}, status_code=400)

    recs_path = Path(__file__).parent.parent.parent / "memory" / "recommendations.json"
    if not recs_path.exists():
        return JSONResponse({"error": "Keine Empfehlungen"}, status_code=404)

    with open(recs_path) as f:
        recs = _json.load(f)

    found = False
    for r in recs:
        if r.get("status") == "open" and (r.get("ticker") == ticker or r.get("ticker", "").split(".")[0] == ticker):
            r["status"] = status
            r["outcome"] = body.get("outcome", f"Manuell geschlossen ({status})")
            found = True

    if found:
        with open(recs_path, "w") as f:
            _json.dump(recs, f, indent=2, ensure_ascii=False)
        return JSONResponse({"status": "ok", "message": f"{ticker} als {status} markiert"})
    else:
        return JSONResponse({"error": f"Keine offene Empfehlung für {ticker}"}, status_code=404)


# ─── Settings API ────────────────────────────────────────────

@app.post("/api/settings")
async def api_save_settings(request: Request):
    """Speichert geänderte Einstellungen."""
    import json as _json
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Ungültiger JSON-Body"}, status_code=400)

    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    with open(settings_path) as f:
        settings = _json.load(f)

    # Nur erlaubte Felder updaten
    if "telegram" in body:
        tg = body["telegram"]
        if "bot_token" in tg:
            settings.setdefault("telegram", {})["bot_token"] = tg["bot_token"]
        if "chat_id" in tg:
            settings.setdefault("telegram", {})["chat_id"] = tg["chat_id"]
    if "brave_search" in body:
        settings.setdefault("brave_search", {})["api_key"] = body["brave_search"].get("api_key", "")
    if "fred" in body:
        settings.setdefault("fred", {})["api_key"] = body["fred"].get("api_key", "")
    if "finnhub" in body:
        settings.setdefault("finnhub", {})["api_key"] = body["finnhub"].get("api_key", "")
    if "user" in body:
        user = body["user"]
        settings.setdefault("user", {})
        if "language" in user:
            settings["user"]["language"] = user["language"]
    if "schedule" in body:
        sched = body["schedule"]
        settings.setdefault("schedule", {})
        if "briefing_days" in sched:
            settings["schedule"]["briefing_days"] = sched["briefing_days"]
        if "briefing_time" in sched:
            settings["schedule"]["briefing_time"] = sched["briefing_time"]
    if "web" in body:
        web = body["web"]
        settings.setdefault("web", {})
        if "port" in web:
            settings["web"]["port"] = int(web["port"])

    with open(settings_path, "w") as f:
        _json.dump(settings, f, indent=2, ensure_ascii=False)

    return JSONResponse({"status": "ok", "message": "Einstellungen gespeichert"})


@app.get("/api/settings")
async def api_get_settings():
    """Gibt aktuelle Einstellungen zurück (API Keys maskiert)."""
    import json as _json
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
    with open(settings_path) as f:
        settings = _json.load(f)

    # API Keys maskieren für die Anzeige
    def mask(key):
        if not key or len(key) < 8:
            return key
        return key[:4] + "..." + key[-4:]

    safe = {
        "telegram": {
            "bot_token": mask(settings.get("telegram", {}).get("bot_token", "")),
            "chat_id": settings.get("telegram", {}).get("chat_id", ""),
        },
        "brave_search": {"api_key": mask(settings.get("brave_search", {}).get("api_key", ""))},
        "fred": {"api_key": mask(settings.get("fred", {}).get("api_key", ""))},
        "finnhub": {"api_key": mask(settings.get("finnhub", {}).get("api_key", ""))},
        "schedule": settings.get("schedule", {}),
        "user": settings.get("user", {}),
        "web": settings.get("web", {}),
    }
    return JSONResponse(safe)


@app.post("/api/refresh")
async def api_refresh(background_tasks: BackgroundTasks):
    global _refresh_running
    async with _refresh_lock:
        if _refresh_running:
            return JSONResponse({"status": "already_running"})
        _refresh_running = True
    background_tasks.add_task(_run_refresh)
    return JSONResponse({"status": "started"})


@app.get("/api/refresh/status")
async def api_refresh_status():
    return JSONResponse({"running": _refresh_running})


async def _run_refresh():
    """Background-Task: Sammelt alle Daten neu und schreibt Cache."""
    global _refresh_running
    try:
        logger.info("Background-Refresh gestartet...")
        from src.data.market import collect_all_market_data, load_portfolio as load_port
        from src.data.macro import collect_all_macro_data
        from src.data.calendar import fetch_earnings_calendar, get_market_status, get_upcoming_macro_events
        import json

        settings_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        with open(settings_path) as f:
            settings = json.load(f)

        portfolio = load_port()
        market_data = collect_all_market_data(portfolio)
        save_cache("market_data", market_data)

        fred_key = settings.get("fred", {}).get("api_key", "")
        macro_data = collect_all_macro_data(fred_key)
        save_cache("macro_data", macro_data)

        tickers = list(market_data.get("positions", {}).keys())
        earnings = fetch_earnings_calendar(tickers)
        market_status = get_market_status()
        macro_events = get_upcoming_macro_events(days_ahead=30)
        save_cache("calendar_data", {
            "earnings": earnings,
            "market_status": market_status,
            "macro_events": macro_events,
        })

        logger.info("Background-Refresh abgeschlossen")
    except Exception as e:
        logger.error(f"Background-Refresh Fehler: {e}")
    finally:
        _refresh_running = False


def run_web_server(host: str = "0.0.0.0", port: int = 8080):
    """Startet den Uvicorn Web-Server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, workers=1, log_level="warning")
