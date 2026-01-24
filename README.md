# Poor Trader Dashboard

A local, real-time dashboard for tracking macro and sentiment indicators used in market analysis. It stores data in SQLite, supports a CLI for fetching/evaluating signals, and serves a FastAPI web UI for quick review.

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
- `api_config.yaml`: optional HTTP data source configuration for private APIs.
- `manual_input.yaml`: optional manual input template (generated via `trader init`).

## Data Storage

The SQLite database is stored at `trader_alerts.sqlite3` in the project root (created automatically).

## Troubleshooting

- Port in use: ensure `127.0.0.1:8501` is available or change `--port`.
- Data missing: refresh the page or run `trader fetch all`.
- Network issues: some sources may be temporarily unavailable or rate-limited.
