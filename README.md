# Poor Trader Dashboard

A local, real-time dashboard for tracking macro and sentiment indicators used in market analysis. It stores data in SQLite, supports a CLI for fetching/evaluating signals, and serves a FastAPI web UI for quick review.

## What This Dashboard Does

This dashboard scrapes free, public market data and turns it into a compact decision panel for trading. A **Top** signal is treated as a **sell** point, and a **Bottom** signal is treated as a **buy** point.

### The 9 Indicators and What They Represent

- US High Yield Option-Adjusted Spread: credit stress and risk appetite in high-yield bonds
- Investor Sentiment Bull-Bear Spread: retail sentiment extremes (bulls minus bears)
- Fear & Greed Index: composite risk sentiment gauge
- Put/Call Ratio (5-Day Average): options positioning and hedging pressure
- S&P 500 Price-to-Earnings Ratio: broad market valuation
- Nasdaq 100 Price-to-Earnings Ratio: growth/tech valuation
- S&P 500 Relative Strength Index (RSI): momentum and overbought/oversold conditions
- Nasdaq 100 Above 20-Day Moving Average: short-term breadth and trend strength
- S&P 500 Volatility Index (VIX): implied volatility and risk aversion

## Live Demo

Access the hosted dashboard here: https://poor-trader-dashboard.onrender.com

## Features

- US High Yield OAS, AAII Bull-Bear Spread, CNN Fear & Greed, Put/Call Ratio, S&P 500 PE, Nasdaq 100 PE, RSI, VIX
- Market overview table with recent performance
- Bull/bear alerts based on historical thresholds
- Local SQLite storage for reproducible views
- CLI utilities for fetch, show, and evaluate

## Quick Start (one-click)

Run the dashboard directly from the project root:

- macOS: double-click `run_dashboard.command`
- Windows: double-click `run_dashboard.cmd`
- Linux: double-click `run_dashboard.py` or run `python3 run_dashboard.py`

The dashboard will open at `http://127.0.0.1:8501`.

## Manual Setup

### Requirements

- Python 3.10+
- Internet connection for live data sources

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-web.txt
pip install -e src/
```

### Run the Web Dashboard

```bash
trader serve --auto-fetch --providers "http,ycharts,cnn,vix,multpl,nasdaqpe,fred,rsi,ndtw"
```

Open `http://127.0.0.1:8501` in your browser.

### Run with Uvicorn Directly (optional)

```bash
python -m uvicorn trader_alerts.web.app:app --host 127.0.0.1 --port 8501 --reload
```

## CLI Usage

```bash
# Show latest values
trader show

# Fetch latest values
trader fetch all

# Evaluate bull/bear alerts
trader evaluate

# Generate template configs
trader init
```

## Configuration

- `FRED_API_KEY` (optional): enables FRED API access for US High Yield OAS.
- `FINNHUB_KEY` (optional): enables Finnhub-powered news on the World Indices map and significant-move annotations on the Index Detail panel. Get a free key at https://finnhub.io/register. You can either export it as an env var (`export FINNHUB_KEY=...`) or drop it on the first line of a file called `finnhub_key.txt` in the project root (already in `.gitignore`). Without it, the map and trend chart still render with prices; news tooltips show a "set FINNHUB_KEY" hint.
- `api_config.yaml`: optional HTTP data source configuration for private APIs.
- `manual_input.yaml`: optional manual input template (generated via `trader init`).

## Global Market Map

Below the indicator and US market panels, the dashboard renders a Global Market Map with markers for the major indices we track:

- US: S&P 500, Dow Jones, Nasdaq
- Europe: FTSE 100, DAX, CAC 40
- Developed Asia: Nikkei 225, Hang Seng, KOSPI, ASX 200, Singapore STI
- Emerging Asia: Shanghai Composite, Sensex, Nifty 50, TWSE

Each marker is colored by the day's % change (green for positive, red for negative). Hovering shows the day's headlines (Finnhub `/company-news` for US ETF proxies SPY/DIA/QQQ; keyword-filtered `/news?category=general` for non-US). Clicking a marker loads that index's 1M / 1Y / All trend curve in the Index Detail panel below, with pin annotations on the largest absolute moves; hover for headline summaries and click for the full per-day article list.

If a price source can't be reached for some indices (e.g., upstream API quota) the dashboard falls back to a deterministic sample value so the map stays complete; the footer shows `Real data X/Y. Missing items fall back to sample values.` and any sample-data marker carries a small `sample` badge in its tooltip.

## Data Storage

The SQLite database is stored at `trader_alerts.sqlite3` in the project root (created automatically).

## Troubleshooting

- Port in use: ensure `127.0.0.1:8501` is available or change `--port`.
- Data missing: refresh the page or run `trader fetch all`.
- Network issues: some sources may be temporarily unavailable or rate-limited.
