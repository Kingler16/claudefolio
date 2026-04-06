# claudefolio

Your AI-powered personal wealth advisor. Automated portfolio monitoring, market analysis, and investment briefings — delivered via Telegram and a self-hosted web dashboard.

Runs on Claude Code with your existing Max/Pro subscription — no API costs.

## What It Does

Twice a week (configurable), claudefolio collects market data for your entire portfolio, pulls macroeconomic indicators, searches for relevant news, and feeds everything into Claude with a specialized financial analyst system prompt. The result is a comprehensive briefing delivered straight to your Telegram and viewable on a professional web dashboard — like having a CFA on retainer.

## Features

### Web Dashboard
- **Portfolio Overview** — KPI cards, allocation donut chart, sortable holdings table
- **Vermögensentwicklung** — TradingView-powered line chart with monthly snapshots
- **Analysis** — Benchmark comparison, monthly returns heatmap, tax-loss harvesting, sector/currency breakdown
- **Market Overview** — Index grid, US/EU macro data, Fear & Greed gauge, earnings calendar
- **Briefing History** — Expandable AI briefings with market regime and key insights
- **Recommendations Tracker** — Active BUY/SELL/WATCH with one-click close, hit-rate tracking
- **Trade Logging** — Log buys/sells directly from the web (auto-closes matching recommendations)
- **Settings Page** — Configure API keys, language, schedule from the browser
- **Dark Theme** — Professional financial dashboard look with accessible colors
- **Responsive** — Works on desktop, tablet, and mobile
- **Multi-Language** — German and English, switchable in settings

### Telegram Bot
- **Bi-weekly Briefings** — Scheduled market analysis with portfolio-specific insights
- **Monthly Reports** — Performance review with optional PDF export
- **On-Demand Analysis** — Send any ticker for a deep-dive
- **Free-Form Chat** — Ask your advisor anything about your portfolio
- **Trade Tracking** — Natural language trade logging (`"Bought 10 AAPL @ 180"`)
- **Watchlist** — Track tickers you're interested in

### Intelligence
- **Persistent Memory** — Remembers past briefings, tracks recommendation outcomes, avoids repetition
- **Tax-Loss Harvesting** — Identifies tax optimization opportunities (configurable tax regime)
- **Benchmark Comparison** — Portfolio vs S&P 500, NASDAQ, DAX, ATX, Gold, BTC
- **Earnings Calendar** — Alerts for upcoming earnings on your positions
- **Insider Activity** — Tracks insider buys/sells
- **Sentiment Analysis** — Finnhub + Bloomberg RSS news sentiment
- **Multi-Account** — Track positions across multiple brokers with EUR/USD conversion
- **Recommendation Dedup** — New recommendations replace old ones for the same ticker

## Screenshots

### Dashboard
Portfolio overview with KPI cards, allocation chart, and holdings table.

### Market
Index grid with descriptions, macro data, and Fear & Greed gauge.

## Architecture

```
claudefolio/
├── config/
│   ├── settings.json            # API keys & schedule (git-ignored)
│   ├── portfolio.json           # Your positions (git-ignored)
│   └── watchlist.json           # Tracked tickers
├── src/
│   ├── main.py                  # Orchestrator (briefing/monthly/analyze/bot/web)
│   ├── data/
│   │   ├── market.py            # Stock prices & fundamentals (yfinance)
│   │   ├── macro.py             # Macro data (FRED, ECB, Fear & Greed)
│   │   ├── news.py              # News (Brave Search, Bloomberg RSS, Finnhub)
│   │   ├── calendar.py          # Earnings & macro event calendar
│   │   └── cache.py             # JSON cache for dashboard
│   ├── analysis/
│   │   ├── claude.py            # Claude Code CLI wrapper
│   │   ├── prompt.py            # System prompt & data formatting
│   │   ├── memory.py            # Persistent memory system
│   │   ├── performance.py       # Benchmarks, tax-loss harvesting
│   │   └── chat_history.py      # Telegram conversation history
│   ├── delivery/
│   │   ├── telegram.py          # Telegram bot & trade logging
│   │   └── pdf_report.py        # Monthly PDF reports (optional)
│   └── web/
│       ├── app.py               # FastAPI application
│       ├── i18n.py              # German/English translations
│       ├── services/
│       │   ├── portfolio_service.py  # Portfolio calculations
│       │   └── cache_service.py      # Cache access layer
│       ├── templates/           # Jinja2 HTML templates
│       └── static/              # CSS, JS, vendored libs
├── memory/                      # Persistent state (git-ignored)
│   ├── cache/                   # Cached market data for dashboard
│   ├── briefings.json           # Past briefing summaries
│   ├── recommendations.json     # Open/closed recommendations
│   └── notes.json               # Market regime, theses, insights
├── scripts/
│   ├── deploy.sh                # Deploy to remote server
│   └── setup_rockpi.sh          # Server setup (RockPi/Raspberry Pi)
├── setup.py                     # Interactive setup wizard
└── requirements.txt
```

### Data Flow

```
[Cron / Telegram / Web Refresh]
        │
        ▼
    main.py (orchestrator)
        │
        ├── data/market.py     → yfinance (prices, fundamentals, insiders)
        ├── data/macro.py      → FRED (US), ECB (EU), CNN Fear & Greed
        ├── data/news.py       → Brave Search + Bloomberg RSS + Finnhub
        └── data/calendar.py   → Earnings dates, macro events
        │
        ├──→ data/cache.py     → JSON cache for web dashboard
        │
        ▼
    analysis/prompt.py         → Builds structured prompt
        │
        ▼
    analysis/claude.py         → Claude Code CLI (--print, Opus, high effort)
        │
        ▼
    analysis/memory.py         → Saves summary, recommendations, theses
        │
        ├──→ delivery/telegram.py  → Telegram message
        └──→ web/app.py            → Web dashboard (reads from cache + memory)
```

### How Claude Is Used

This project does **not** use the Claude API directly. Instead, it shells out to the [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) in `--print` mode:

- No API key needed for Claude — uses your Max/Pro subscription
- Access to Opus model with high effort mode
- Prompts via stdin (no length limits)
- Auto-detects CLI path for cron/systemd environments

## Prerequisites

- **Python 3.11+**
- **Claude Code CLI** — requires Claude Max or Pro subscription
  - Install: `npm install -g @anthropic-ai/claude-code`
  - Authenticate: `claude auth`
- **Telegram Bot** — create via [@BotFather](https://t.me/BotFather)

Optional but recommended:
- **Brave Search API** — free tier (2,000/month) at [brave.com/search/api](https://brave.com/search/api/)
- **FRED API** — free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)
- **Finnhub API** — free at [finnhub.io](https://finnhub.io/)

## Quick Start

```bash
git clone https://github.com/Kingler16/claudefolio.git
cd claudefolio

# Interactive setup wizard
python3 setup.py

# Activate virtual environment
source venv/bin/activate

# Run your first briefing
python -m src.main briefing

# Start the Telegram bot
python -m src.main bot

# Start the web dashboard
python -m src.main web
# → Open http://localhost:8080
```

The setup wizard guides you through language selection, country & tax regime, Telegram setup, API keys, briefing schedule, and portfolio import (CSV or manual).

## Running Modes

```bash
python -m src.main briefing              # Bi-weekly briefing (for cron)
python -m src.main monthly               # Monthly report (for cron)
python -m src.main analyze --ticker AAPL  # On-demand analysis
python -m src.main bot                    # Telegram bot (long-running)
python -m src.main web                    # Web dashboard (long-running)
python -m src.main web --port 3000       # Custom port
```

## Web Dashboard

The dashboard is built with FastAPI + Jinja2 + HTMX + Chart.js — no Node.js build step required. It reads from the same data cache that briefings write to, so you always see up-to-date information.

| Page | Features |
|------|----------|
| **Dashboard** | KPI cards, allocation donut, TradingView chart, holdings table |
| **Portfolio** | Per-account breakdown, currency/sector charts, trade logging |
| **Analysis** | Benchmarks, monthly heatmap, tax-loss harvesting, top/bottom performers |
| **Market** | Indices, US/EU macro, Fear & Greed, earnings calendar |
| **Briefings** | AI briefing history, market regime, key insights, investment theses |
| **Recommendations** | BUY/SELL/WATCH tracker with close/cancel, hit-rate stats |
| **Settings** | API keys, language (de/en), schedule, portfolio overview |

The "Refresh" button triggers a background data collection. On first start, data is collected automatically.

## Telegram Bot Commands

| Input | Action |
|-------|--------|
| `/status` | Portfolio overview |
| `/briefing` | Trigger on-demand briefing |
| `/log` | Step-by-step trade form |
| `/help` | Help message |
| `AAPL` | Analyze a ticker |
| `watch RKLB` | Add to watchlist |
| `unwatch RKLB` | Remove from watchlist |
| `Bought 10 AAPL @ 180` | Log a buy |
| `Sold 5 TSLA @ 250` | Log a sell |
| *Any text* | Chat with your AI advisor |

Trades logged via Telegram or the web dashboard automatically close matching open recommendations.

## Configuration

All settings can be configured via the **Settings page** on the web dashboard, or by editing `config/settings.json` directly:

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

## Deployment (Raspberry Pi / RockPi / Any Linux Server)

Designed to run on a low-power always-on device (~90MB RAM total).

```bash
# From your local machine
cd scripts
./deploy.sh admin@192.168.1.27

# On the server
cd ~/claudefolio
bash scripts/setup_rockpi.sh
```

This sets up:
- Python venv + dependencies
- Cron jobs for scheduled briefings
- systemd services for Telegram bot + web dashboard (auto-start on boot)

### systemd Services

```bash
sudo systemctl status claudefolio-bot   # Telegram bot
sudo systemctl status claudefolio-web   # Web dashboard
```

Both services restart automatically on crash and start on boot.

## API Rate Limits & Costs

| Service | Cost | Notes |
|---------|------|-------|
| Claude Code CLI | Included in Max ($100/mo) or Pro ($20/mo) | No separate API costs |
| yfinance | Free | No API key needed |
| Brave Search | Free tier: 2,000/month | Sufficient for 2 briefings/week |
| FRED | Free | Generous limits |
| Finnhub | Free tier: 60 calls/min | Sentiment + news |
| ECB Data API | Free | No key needed |

## Disclaimer

This software is for **educational and informational purposes only**. It does not constitute financial advice.

- AI-generated analysis may contain errors or hallucinations
- Past recommendation performance does not guarantee future results
- Always do your own research before making investment decisions
- The authors accept no liability for financial losses

## License

MIT
