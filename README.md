# Poor Trader Dashboard

A real-time dashboard that turns a curated set of macro, valuation and
sentiment indicators into a compact decision panel for trading. It runs on
Cloudflare Workers + Pages with a D1 (SQLite) backing store, exposes a
small JSON API, and ships a single-page front end with charts, world map,
indicator history, market regime composite, and a watchlist.

Live site: **https://poortrader.com/**

> A **Top** reading is treated as a *sell / take-profit* signal; a
> **Bottom** reading is treated as a *buy / accumulate* signal. Every
> threshold below is derived from historical highs and lows around the
> tops and bottoms after 2000 — see the *History* section in app.

## Why This Exists

We picked the small set of public indicators that have historically shown
the **strongest correlation with major US equity tops and bottoms**, and
wrote a single composite algorithm — the **Poor2Rich algorithm** —
that fuses them into one score predicting potential buy windows and
drawdown risks.

The dashboard is intentionally compact: one screen, one regime score,
clickable indicators with full history, contextual news, and a watchlist
that can be reordered or sorted on the fly.

## Tracked Indicators

| Indicator | Why it matters |
|---|---|
| **US High Yield Option-Adjusted Spread (HY OAS)** | Cleanest credit-stress signal — credit usually moves before equities. |
| **Investor Sentiment Bull-Bear Spread (AAII)** | Retail sentiment extremes — contrarian by construction. |
| **CNN Fear & Greed Index** | Composite of seven sub-indicators of risk appetite. |
| **Put/Call Ratio (5-Day Average)** | Options positioning and hedging pressure. |
| **S&P 500 Price-to-Earnings (PE) Ratio** | Broad market valuation anchor. |
| **Nasdaq 100 PE Ratio** | Growth / tech valuation. |
| **S&P 500 RSI(14)** (Wilder smoothing) | Price momentum, overbought / oversold. |
| **Nasdaq 100 % Above 20-Day MA** | Short-term breadth thrust / capitulation. |
| **S&P 500 VIX** | Implied volatility / risk aversion. |
| **CBOE SKEW** | Institutional tail-risk hedging. |
| **10Y–2Y Treasury Yield Curve** | Late-cycle / Fed-easing detection. |

All values are pulled from public APIs (FRED, Yahoo Finance, CNN dataviz,
multpl, Barron's, Barchart). Each indicator is timestamped, written into
D1, and rendered on the front end with its top/bottom threshold lines and
optional shaded zones.

## The Poor2Rich Algorithm

The Poor2Rich algorithm produces a single signed score that classifies
the market into one of seven regimes — from **Strong Buy** to **Strong
Risk** — and explains itself with a per-indicator contribution
breakdown.

### Formula

```
score = Σᵢ tier(xᵢ) × wᵢ
```

* `xᵢ` — the latest reading of indicator *i*
* `tier(xᵢ)` — a signed extremeness tier in `{-3, -2, -1, 0, +1, +2, +3}`,
  derived from how extreme the value is vs. its historical top/bottom
  thresholds (e.g. RSI < 25 = +2, RSI > 80 = −2).
* `wᵢ` — a quality weight reflecting how reliably the indicator has
  marked tops/bottoms historically.

Positive contributions push the score toward a **buy / bottom** bias;
negative contributions push toward a **top / risk** bias.

### Indicator Weights

| Weight | Indicator | Rationale |
|---|---|---|
| 1.5 | VIX | Real-time, hard to game. |
| 1.5 | HY OAS | Cleanest credit-stress signal. |
| 1.2 | S&P 500 PE | Valuation anchor. |
| 1.0 | CNN Fear & Greed | Composite sentiment. |
| 1.0 | Put/Call (5d) | Options-flow sentiment. |
| 1.0 | NDX > 20d MA | Market breadth. |
| 1.0 | 10Y–2Y Curve | Macro late-cycle. |
| 0.7 | AAII Bull-Bear | Noisy weekly survey. |
| 0.7 | S&P 500 RSI | Price momentum. |
| 0.7 | NDX 100 PE | Less standard. |
| 0.6 | CBOE SKEW | Indirect, top-only. |

### Regime Bands

| Band | Range |
|---|---|
| Strong Buy | ≥ +9.0 |
| Buy | +4.5 to +9.0 |
| Cautious Buy | +1.5 to +4.5 |
| Neutral | −1.5 to +1.5 |
| Caution | −4.5 to −1.5 |
| Risk | −9.0 to −4.5 |
| Strong Risk | ≤ −9.0 |

The regime card on the dashboard shows the active band, the cumulative
buy/risk points, and which indicators drove each side.

## Features

* **Indicator panel** — latest value with top/bottom highlighting; click
  any row to see its full historical line chart with threshold lines,
  shaded zones, and per-point colored markers (green/red/white).
* **Market Regime composite** — Poor2Rich score, active band, indicator
  contributions, and regime band legend.
* **Bull/Bear alert table** — simplified per-indicator rules (≥ / ≤
  thresholds) with rule descriptions.
* **Watchlist (Stocks)** — searchable, addable, removable; sortable by
  1W / 1M / 3M / 1Y change; drag-and-drop or **Top** button to reorder;
  click any row to load its detail.
* **Stock Detail panel** — 1M – 5Y chart, biggest-move dots that open
  matching news, last 30 days of headlines (Finnhub).
* **Global Market Map** — colored dots for major indices (US, Europe,
  Developed Asia, Emerging Asia); hover for headlines, click to load
  the index detail.
* **Index Detail** — 1M / 3M / 6M / 1Y / 2Y / 5Y / All chart with
  significant-move pins; click a pin for full per-day news.
* **Historical comparison table** — major top/bottom events since 2000
  with HY OAS, AAII, F&G, PE readings at peak vs. trough.
* **Hourly cron** — D1 is refreshed every hour on the hour with a
  heartbeat so the *Last Updated* timestamp keeps moving.

## Architecture

```
   ┌──────────────┐        fetch / hourly cron        ┌──────────┐
   │  Cloudflare  │ ─────────────────────────────────▶│   FRED   │
   │   Worker     │ ─────────────────────────────────▶│ Yahoo    │
   │ (TypeScript) │ ─────────────────────────────────▶│ CNN, …   │
   └──────┬───────┘                                   └──────────┘
          │                                                  
          │ D1 (SQLite) — observations, market_overview,    
          │ news_cache, kv_store (heartbeat + rate limits)  
          │                                                  
          ▼                                                  
   ┌──────────────┐                                          
   │  /api/*      │  latest, alerts, regime, indicator-     
   │   JSON API   │  history, market-overview, stock-       
   │              │  detail, world-indices, index-history,  
   │              │  index-news, refresh, status            
   └──────┬───────┘                                          
          │                                                  
          ▼                                                  
   ┌──────────────┐                                          
   │  Pages SPA   │  Chart.js + ECharts; vanilla JS         
   └──────────────┘                                          
```

* **Frontend**: `cloudflare/pages/index.html`, single page, Chart.js for
  indicator history, ECharts for world map / stock detail / index
  detail.
* **Backend**: `cloudflare/worker/` (Cloudflare Worker + D1).
* **Schema**: `cloudflare/schema.sql`.

## Running Locally

### Prerequisites

* Node 18+
* `npm i -g wrangler` (or `npx wrangler`)
* A Cloudflare account with D1 access (free tier is enough).

### Worker (API)

```bash
cd cloudflare/worker
npm install

# Create the D1 database the first time
wrangler d1 create poor-trader-db
# Paste the returned database_id into wrangler.toml

# Apply schema
wrangler d1 execute poor-trader-db --remote --file=../schema.sql

# Optional secrets (leave unset if you don't have keys)
wrangler secret put FINNHUB_KEY   # enables stock + map news
wrangler secret put FRED_API_KEY  # enables HY OAS + yield curve

# Local dev
wrangler dev

# Deploy
wrangler deploy
```

### Pages (Frontend)

```bash
cd cloudflare/worker
# Point the SPA at your Worker URL by editing
#   window.API_BASE = "..."
# at the bottom of cloudflare/pages/index.html, then deploy:
wrangler pages deploy ../pages --project-name poor-trader-dashboard
```

### Cron Schedule

Defined in `cloudflare/worker/wrangler.toml`:

```toml
[triggers]
crons = ["0 * * * *"]   # top of every hour
```

Each run pulls every available source and writes a heartbeat into the
`kv_store` table so the dashboard's *Last Updated* stamp advances even
when no upstream value changed.

## API

| Endpoint | Description |
|---|---|
| `GET /api/latest` | Latest value per indicator + top/bottom flags. |
| `GET /api/alerts` | Bull/bear rule evaluation per indicator. |
| `GET /api/regime` | Poor2Rich score, band, per-indicator contributions. |
| `GET /api/indicator-history?indicator_id=…&days=…` | Time series for one indicator with thresholds. |
| `GET /api/market-overview?symbols=AAPL,MSFT&refresh=1` | Latest close + 1W/1M/3M/1Y for indices, futures, crypto, watchlist. |
| `GET /api/stock-detail?symbol=…&range=1y` | OHLC series + Finnhub news for the last 30 days. |
| `GET /api/world-indices` | Latest close + headlines for major world indices. |
| `GET /api/index-history?symbol=…&range=…` | Index time series + significant moves with news. |
| `GET /api/index-news?symbol=…&date=…` | Per-day news for an index. |
| `POST /api/refresh` | Trigger an out-of-cycle refresh (rate-limited per IP). |
| `GET /api/status` | Heartbeat + which secrets are wired. |

## Configuration

* `FRED_API_KEY` *(secret)* — enables FRED-backed HY OAS and 10Y–2Y curve.
* `FINNHUB_KEY` *(secret)* — enables company-news on the watchlist and
  general-news on the world map. Get a free key at
  https://finnhub.io/register.

## Disclaimer

This is a research / hobby project. The Poor2Rich score and bull/bear
alerts are *early-warning gauges* of sentiment and credit temperature —
**not** trading orders. Always combine with position sizing and risk
controls.
