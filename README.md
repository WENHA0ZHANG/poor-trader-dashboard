# Poor Trader Dashboard

**A decision-support dashboard for timing market risk and opportunity.**

Poor Trader Dashboard is an open, free-to-use research assistant for
investors and traders. It combines multiple high-correlation macro,
valuation, sentiment, volatility and breadth indicators into one
transparent algorithm — the **Poor2Rich score** — to help users identify
potential buying windows, take-profit zones and drawdown-risk periods in
the US equity market.

🌐 **Live: https://poortrader.com/**

It runs entirely on Cloudflare Workers + Pages with a D1 (SQLite) backing
store, refreshes hourly, and is designed for fast decision review: check
the current regime, inspect the signal drivers, then drill into charts,
news and history when a score needs confirmation.

## Purpose

Most market dashboards either bury the user in dozens of unrelated charts
or return a black-box score with no explanation. Poor Trader Dashboard is
designed to turn public market data into a practical decision framework:

- **Decision support, not blind automation.** The Poor2Rich score is an
  evidence layer for trading decisions. It highlights whether the market
  is closer to a bottom-risk/reward setup or a top/drawdown-risk setup,
  while still leaving final judgment to the user.
- **A focused indicator set.** The model uses a small group of indicators
  with strong historical relationships to major US equity tops and
  bottoms, instead of adding every available metric.
- **Every input is auditable.** Every contribution to the score is
  itemised on screen, every indicator is plotted against its historical
  top / bottom thresholds, and every threshold was calibrated against
  the actual major US equity tops and bottoms since 2000.
- **Context around the score.** Watchlist performance, global index
  movements, significant-move markers and news sit next to the model, so
  users can verify whether the signal matches current market context.
- **Free, fast, hosted.** No login, no install, no API key. The site is
  edge-served, refreshed hourly, and available at `poortrader.com`.

> A **Top** reading is treated as a *sell / take-profit* signal; a
> **Bottom** reading is treated as a *buy / accumulate* signal. Every
> threshold is derived from historical extremes around the major US
> equity tops and bottoms since 2000 — see the in-app *History* section
> on page 4 for the side-by-side numbers.

---

<h2 align="center">📊 Signal Track Record</h2>

<p align="center">
  <em>Every signal is logged with its full score breakdown on the date it fired,
  so the model is judged by outcomes — not hindsight.</em>
</p>

<br>

<!-- ── 2026-03-30 · BOTTOM CALL ──────────────────────────────────────────── -->

<table align="center">
<tr>
<td>

<h3>🟢 2026-03-30 · Bottom Call &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/regime-Buy-22c55e?style=for-the-badge" alt="Buy">
  <img src="https://img.shields.io/badge/score-+6.40-22c55e?style=for-the-badge" alt="+6.40">
  <img src="https://img.shields.io/badge/result-✓ confirmed-16a34a?style=for-the-badge" alt="Confirmed">
</h3>

Poor2Rich flagged a **Buy** regime on **2026-03-30** — volatility,
fear, breadth and momentum all simultaneously stretched toward
capitulation levels. The S&P 500 reversed upward in the following
sessions, confirming the bottom window.

<table>
<thead>
<tr>
  <th>Component</th>
  <th align="right">Reading</th>
  <th align="center">Tier</th>
  <th align="center">Weight</th>
  <th align="right">Points</th>
</tr>
</thead>
<tbody>
<tr bgcolor="#052e16">
  <td>🟢 VIX</td><td align="right">30.61</td>
  <td align="center">+2</td><td align="center">1.5</td>
  <td align="right"><strong>+3.00</strong></td>
</tr>
<tr bgcolor="#052e16">
  <td>🟢 Fear & Greed Index</td><td align="right">13.69</td>
  <td align="center">+2</td><td align="center">1.0</td>
  <td align="right"><strong>+2.00</strong></td>
</tr>
<tr bgcolor="#052e16">
  <td>🟢 NDX > 20d MA</td><td align="right">18.81%</td>
  <td align="center">+1</td><td align="center">1.0</td>
  <td align="right"><strong>+1.00</strong></td>
</tr>
<tr bgcolor="#052e16">
  <td>🟢 AAII Bull-Bear</td><td align="right">-21.60%</td>
  <td align="center">+1</td><td align="center">0.7</td>
  <td align="right"><strong>+0.70</strong></td>
</tr>
<tr bgcolor="#052e16">
  <td>🟢 S&P 500 RSI(14)</td><td align="right">27.72</td>
  <td align="center">+1</td><td align="center">0.7</td>
  <td align="right"><strong>+0.70</strong></td>
</tr>
<tr bgcolor="#450a0a">
  <td>🔴 10Y-2Y Curve</td><td align="right">+0.53%</td>
  <td align="center">-1</td><td align="center">1.0</td>
  <td align="right"><strong>-1.00</strong></td>
</tr>
<tr>
  <td><em>Other indicators</em></td><td align="right">Normal range</td>
  <td align="center">0</td><td align="center">—</td>
  <td align="right">0.00</td>
</tr>
</tbody>
</table>

<p align="center">
  <img src="https://img.shields.io/badge/Buy_points-+7.40-22c55e?style=flat-square" alt="+7.40">
  &nbsp;
  <img src="https://img.shields.io/badge/Risk_points--1.00-ef4444?style=flat-square" alt="-1.00">
  &nbsp;
  <img src="https://img.shields.io/badge/Composite-+6.40_(Buy)-22c55e?style=flat-square&labelColor=064e3b" alt="+6.40 Buy">
</p>

</td>
</tr>
</table>

---

## The Pages

The site is organised into four numbered pages — clicking the
**Poor Trader Dashboard** title in the header always returns to page 01.

### 01 · Prediction
The home page and the core of the system.

- **Indicator Trends & Latest Values** — every indicator with its
  latest reading, formatted top/bottom flag, and source. Click any row
  to load its full history with threshold lines, shaded extreme zones,
  and per-point colored hover markers.
- **Market Regime — Composite View** — the live Poor2Rich score, the
  active regime band, the cumulative *Buy / Caution / Risk* points, the
  per-indicator contribution table, and the full band legend.

### 02 · Market
Performance and watchlist tracking.

- **Indices**, **Other Assets** (gold, oil, BTC, USD, treasuries) and
  **Stocks** tables — latest close plus 1W / 1M / 3M / 1Y change, with
  sortable headers (descending → ascending → reset) on every period
  column.
- **Watchlist** — add or remove tickers, drag-and-drop to reorder, or
  hit **T** to pin a ticker to the top. Selections persist in the
  browser.
- **Stock Detail** — click any stock to load its multi-range chart
  (1M / 3M / 6M / 1Y / 2Y / 5Y / All) with biggest-move dots; click a
  dot to read the news that day plus the most recent 30 days of
  Finnhub headlines for the ticker.

### 03 · Global Map & News
The world view.

- **Interactive global index map** — colored dots for the major US,
  European, Developed-Asia and Emerging-Asia indices. Hover a country
  for headlines, click to load its detail panel.
- **Index Detail** — multi-range price chart with significant-move
  pins; click a pin to expand its associated news.
- **General market news feed** — fresh global headlines from Finnhub
  to keep context next to the chart.

### 04 · Signals & History
Rules and historical reference.

- **Bull / Bear Alerts** — the simplified per-indicator rules (≥ / ≤
  thresholds) the dashboard uses to flag tops and bottoms, with their
  rationale.
- **Historical Comparison** — every major US equity top and bottom
  since 2000 with the readings of HY OAS, AAII, F&G and PE at the
  peak vs. the trough — the same database the thresholds are
  calibrated against.

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

## Platform Capabilities

Beyond the per-page content, the platform provides:

* **Hourly refresh.** A Cloudflare cron pulls every source on the hour
  and updates a heartbeat so the in-app *Last Updated* timestamp always
  reflects the most recent run, even when no upstream value changed.
* **On-demand refresh.** The header's **Update** button triggers an
  out-of-cycle pull (rate-limited per IP) for users who want the
  freshest snapshot without waiting for the next cron.
* **Persistent personalisation.** Watchlist additions, deletions,
  manual order, and column sort live in `localStorage` — your view is
  remembered across visits.
* **Mobile-friendly single page.** Tabbed navigation, no full-page
  reloads, instant page switching, charts auto-resize.
* **Open JSON API.** Every screen is backed by a public, no-auth REST
  endpoint, so you can build your own bots, alerts or dashboards on top
  (see the API table below).
* **Edge-cached static, never-cached data.** The HTML / JS is served
  from Cloudflare Pages; the data API explicitly opts out of every
  cache layer so you never see a stale score.

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
