```
    ██╗   ██╗███████╗██╗      ██████╗ ██████╗  █████╗
    ██║   ██║██╔════╝██║     ██╔═══██╗██╔══██╗██╔══██╗
    ██║   ██║█████╗  ██║     ██║   ██║██████╔╝███████║
    ╚██╗ ██╔╝██╔══╝  ██║     ██║   ██║██╔══██╗██╔══██║
     ╚████╔╝ ███████╗███████╗╚██████╔╝██║  ██║██║  ██║
      ╚═══╝  ╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
```

**Your AI-powered personal wealth advisor.** Automated portfolio monitoring, market analysis, and investment briefings — delivered via a self-hosted web dashboard and Telegram bot.

Runs on Claude Code with your existing Max/Pro subscription — zero API costs for AI.

---

## What It Does

Twice a week, Velora collects market data for your entire portfolio, pulls macroeconomic indicators, searches for relevant news, and feeds everything into Claude Opus with a specialized financial analyst system prompt. The result is a comprehensive briefing delivered to your Telegram and viewable on a professional dark-themed web dashboard — like having a CFA on retainer.

## Features

| Category | Highlights |
|----------|------------|
| **Web Dashboard** | 7 pages: Dashboard, Portfolio, Analysis, Market, Briefings, Recommendations, Settings. Dark theme, responsive, multi-language (de/en) |
| **Telegram Bot** | Briefings, trade logging (natural language), ticker analysis, free-form chat, watchlist |
| **AI Analysis** | Bi-weekly briefings, monthly reports, on-demand deep-dives, persistent memory across sessions |
| **Portfolio Tracking** | Multi-account, multi-currency (EUR/USD), tax-loss harvesting, benchmark comparison |
| **Recommendations** | BUY/SELL/WATCH tracking, automatic outcome detection, hit-rate stats, trade auto-close |
| **Data Sources** | yfinance, FRED, ECB, Brave Search, Bloomberg RSS, Finnhub, CNN Fear & Greed |
| **Deployment** | Runs on Raspberry Pi (~90MB RAM), systemd auto-start, cron scheduling |

## Example Briefing

```
MARKTLAGE

Relief-Rally (NASDAQ +4.4%, VIX -22%) ändert nichts am Extreme-Fear-Regime.
Yield Curve normal (+52bps), aber Credit Spreads weiten sich.

PORTFOLIO-CHECK

ASML: Stärkster Gewinner (+63% total), aber underperformed am Rally-Tag.
Stop-Loss bei 1050 EUR empfohlen vor Earnings am 15.4.

Gold ETC: -1.8% in EUR trotz +3.4% Goldpreis in USD — der EUR/USD-Effekt.

EMPFEHLUNGEN

Keine neuen Trades. 14 von 17 Positionen reporten in den nächsten 6 Wochen.
Cash-Quote von 31% ist im Extreme-Fear-Umfeld eine Stärke. Abwarten.
```

## Quick Start

```bash
git clone https://github.com/Kingler16/velora.git
cd velora

python3 setup.py          # Interactive setup wizard
source venv/bin/activate

python -m src.main briefing   # First AI briefing
python -m src.main bot        # Start Telegram bot
python -m src.main web        # Start web dashboard → http://localhost:8080
```

The setup wizard guides you through: language, country & tax regime, Telegram bot, API keys, briefing schedule, and portfolio import (CSV or manual).

## Prerequisites

- **Python 3.11+**
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code` (requires Claude Max or Pro)
- **Telegram Bot** — create via [@BotFather](https://t.me/BotFather)
- Optional: [Brave Search API](https://brave.com/search/api/), [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html), [Finnhub API](https://finnhub.io/) (all free tier)

## Web Dashboard

Built with FastAPI + Jinja2 + HTMX + Chart.js + TradingView Lightweight Charts. No Node.js needed.

| Page | What It Shows |
|------|---------------|
| **Dashboard** | KPI cards, allocation donut, portfolio history chart, sortable holdings table, index ticker bar |
| **Portfolio** | Per-account breakdown, currency/sector charts, bank accounts, trade logging modal |
| **Analysis** | Benchmark bar chart, monthly returns heatmap, tax-loss harvesting, top/bottom performers |
| **Market** | 9 indices with descriptions, US/EU macro data, Fear & Greed gauge, earnings calendar |
| **Briefings** | Market regime, key insights, expandable briefing history with full text |
| **Recommendations** | Active BUY/SELL cards, WATCH/HOLD watchlist, one-click close, hit-rate KPIs |
| **Settings** | API keys, language (de/en), briefing schedule, portfolio overview |

Start with `python -m src.main web` and open `http://localhost:8080`.

## Telegram Bot

| Input | Action |
|-------|--------|
| `/status` | Portfolio overview |
| `/briefing` | Trigger AI briefing |
| `/log` | Step-by-step trade form |
| `AAPL` | Deep-dive ticker analysis |
| `watch RKLB` / `unwatch RKLB` | Manage watchlist |
| `Bought 10 AAPL @ 180` | Log a trade (natural language, de/en) |
| *Any text* | Chat with your AI advisor |

Trades logged via Telegram or the web dashboard automatically close matching AI recommendations.

## Architecture

```
[Cron / Telegram / Web Refresh]
        │
        ▼
    main.py ─── data/market.py    → yfinance
        │   ├── data/macro.py     → FRED + ECB + Fear & Greed
        │   ├── data/news.py      → Brave + Bloomberg + Finnhub
        │   └── data/calendar.py  → Earnings + events
        │
        ├──→ cache.py → memory/cache/  → Web Dashboard (FastAPI)
        │
        ▼
    analysis/claude.py → Claude Code CLI (Opus, high effort)
        │
        ▼
    memory.py → briefings, recommendations, theses
        │
        └──→ telegram.py → Telegram message
```

### How Claude Is Used

Velora does **not** call the Claude API directly. It shells out to [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) in `--print` mode — no API key needed, uses your Max/Pro subscription, Opus model with high effort, prompts via stdin.

## Running Modes

```bash
python -m src.main briefing              # Bi-weekly briefing (for cron)
python -m src.main monthly               # Monthly report (for cron)
python -m src.main analyze --ticker AAPL  # On-demand analysis
python -m src.main bot                    # Telegram bot (long-running)
python -m src.main web                    # Web dashboard (long-running)
python -m src.main web --port 3000       # Custom port
```

## Configuration

All settings configurable via the web dashboard Settings page or `config/settings.json`:

| Key | Description |
|-----|-------------|
| `telegram.bot_token` | Bot token from @BotFather |
| `telegram.chat_id` | Your Telegram chat ID |
| `brave_search.api_key` | Brave Search API key |
| `fred.api_key` | FRED API key |
| `finnhub.api_key` | Finnhub API key |
| `schedule.briefing_days` | e.g. `["monday", "thursday"]` |
| `schedule.briefing_time` | e.g. `"07:00"` |
| `user.language` | `"de"` or `"en"` |
| `web.port` | Dashboard port (default: 8080) |

## Deployment

Designed for always-on low-power devices (~90MB RAM).

```bash
# Deploy from local machine
cd scripts && ./deploy.sh admin@your-server-ip

# On the server
cd ~/velora && bash scripts/setup_rockpi.sh
```

Sets up: Python venv, Claude CLI, cron jobs (briefing + monthly), systemd services (bot + web dashboard with auto-start on boot).

```bash
sudo systemctl status velora-bot    # Telegram bot
sudo systemctl status velora-web    # Web dashboard
```

## API Costs

| Service | Cost | Notes |
|---------|------|-------|
| Claude Code CLI | Included in Max ($100/mo) or Pro ($20/mo) | No separate API costs |
| yfinance | Free | No API key needed |
| Brave Search | Free tier: 2,000/month | Sufficient for 2 briefings/week |
| FRED / ECB | Free | US + EU macro data |
| Finnhub | Free tier: 60 calls/min | Sentiment + news |

## Disclaimer

For **educational and informational purposes only**. Not financial advice. AI analysis may contain errors. Always do your own research. No liability for financial losses.

## License

MIT
