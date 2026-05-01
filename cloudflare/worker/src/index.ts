import type { Env } from "./lib/types";
import { ALL_INDICATOR_IDS } from "./lib/types";
import {
  getLatestObservations,
  getRecentObservations,
  upsertObservations,
  getLastUpdateTime,
  setLastCronRun,
  getMarketOverviewRows,
  upsertMarketOverviewRows,
  getNewsCacheEntry,
  upsertNewsCache,
} from "./lib/db";
import { computeSignals } from "./lib/signals";
import { computeMarketRegime } from "./lib/regime";
import { fetchYahooChart } from "./lib/yahoo";
import { fetchStooqDailyCloses, fetchStooqQuote } from "./lib/stooq";
import { fetchCompanyNews, fetchGeneralNews, newsTickerForYahooSymbol } from "./lib/finnhub";
import { fetchAllProviders } from "./lib/fetchers";
import { WORLD_INDICES, getIndexMeta } from "./lib/world";

// ── CORS helpers ─────────────────────────────────────────────────────────────
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      // All API responses are dynamic — never let Cloudflare's edge or the
      // browser cache them, otherwise the dashboard can show a stale
      // "Last Updated" timestamp depending on which edge / cache hop is hit.
      "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      "CDN-Cache-Control": "no-store",
      "Cloudflare-CDN-Cache-Control": "no-store",
      ...CORS,
    },
  });
}

function err(msg: string, status = 400): Response {
  return json({ error: msg }, status);
}

// ── Indicator metadata ────────────────────────────────────────────────────────
const INDICATOR_NAMES: Record<string, string> = {
  us_high_yield_spread:    "US High Yield Option-Adjusted Spread",
  bofa_bull_bear:          "Investor Sentiment Bull-Bear Spread",
  cnn_fear_greed_index:    "Fear & Greed Index",
  cnn_put_call_options:    "Put/Call Ratio (5-Day Average)",
  sp500_pe_ratio:          "S&P 500 Price-to-Earnings Ratio",
  nasdaq100_pe_ratio:      "Nasdaq 100 Price-to-Earnings Ratio",
  sp500_rsi:               "S&P 500 Relative Strength Index",
  nasdaq100_above_20d_ma:  "Nasdaq 100 Above 20-Day Moving Average (%)",
  vix:                     "S&P 500 Volatility Index",
  cboe_skew:               "CBOE SKEW (Tail-Risk Hedging)",
  yc_10y_2y:               "10Y-2Y Treasury Yield Curve",
};

const INDICATOR_SOURCE_URLS: Record<string, string> = {
  us_high_yield_spread:   "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
  bofa_bull_bear:         "https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread",
  cnn_fear_greed_index:   "https://edition.cnn.com/markets/fear-and-greed",
  cnn_put_call_options:   "https://edition.cnn.com/markets/fear-and-greed",
  sp500_pe_ratio:         "https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
  nasdaq100_pe_ratio:     "https://worldperatio.com/index/nasdaq-100/",
  sp500_rsi:              "https://www.investing.com/indices/us-spx-500-technical",
  nasdaq100_above_20d_ma: "https://www.barchart.com/stocks/quotes/$NDTW",
  vix:                    "https://edition.cnn.com/markets/fear-and-greed",
  cboe_skew:              "https://finance.yahoo.com/quote/%5ESKEW",
  yc_10y_2y:              "https://fred.stlouisfed.org/series/T10Y2Y",
};

const INDICATOR_THRESHOLDS: Record<string, { top?: number; bottom?: number; top_zone?: number[] }> = {
  bofa_bull_bear:         { top: 20.0, bottom: -20.0 },
  cnn_fear_greed_index:   { top: 75.0, bottom: 25.0 },
  cnn_put_call_options:   { top: 0.55, bottom: 0.95 },
  vix:                    { top: 14.0, bottom: 25.0 },
  sp500_rsi:              { top: 70.0, bottom: 30.0 },
  sp500_pe_ratio:         { top: 30.0, bottom: 20.0 },
  nasdaq100_pe_ratio:     { top: 35.0, bottom: 22.0 },
  nasdaq100_above_20d_ma: { top: 80.0, bottom: 20.0 },
  us_high_yield_spread:   { top: 2.8, bottom: 4.5 },
  cboe_skew:              { top: 155.0 },
  yc_10y_2y:              { top_zone: [-0.05, 0.6] },
};

// ── Default market symbols ────────────────────────────────────────────────────
const DEFAULT_MARKET_SYMBOLS = [
  "^spx", "^dji", "^ndq",
  "btc.v", "xauusd", "xagusd",
  "nvo.us", "aapl.us", "goog.us", "nvda.us", "tsla.us",
  "meta.us", "msft.us", "hood.us", "mu.us",
  "brk-b.us", "rklb.us", "amzn.us", "ko.us", "zeta.us", "q.us", "sols.us",
];

// `name` is the display label the SPA uses in the market tables — keep it
// stable even when Yahoo's own ticker looks different (e.g. ^GSPC vs ^SPX,
// GC=F vs XAU, BTC-USD vs BTC). Previously we wrote `name: yahooSym` into
// D1 which caused the Reload button to "rename" rows to their Yahoo slugs.
const DEFAULT_ITEMS: Array<{ symbol: string; yahoo: string; name: string }> = [
  { symbol: "^spx",     yahoo: "^GSPC",   name: "^SPX"  },
  { symbol: "^dji",     yahoo: "^DJI",    name: "^DJI"  },
  { symbol: "^ndq",     yahoo: "^IXIC",   name: "^NDQ"  },
  { symbol: "btc.v",    yahoo: "BTC-USD", name: "BTC"   },
  { symbol: "xauusd",   yahoo: "GC=F",    name: "XAU"   },
  { symbol: "xagusd",   yahoo: "SI=F",    name: "XAG"   },
  { symbol: "nvo.us",   yahoo: "NVO",     name: "NVO"   },
  { symbol: "aapl.us",  yahoo: "AAPL",    name: "AAPL"  },
  { symbol: "goog.us",  yahoo: "GOOG",    name: "GOOG"  },
  { symbol: "nvda.us",  yahoo: "NVDA",    name: "NVDA"  },
  { symbol: "tsla.us",  yahoo: "TSLA",    name: "TSLA"  },
  { symbol: "meta.us",  yahoo: "META",    name: "META"  },
  { symbol: "msft.us",  yahoo: "MSFT",    name: "MSFT"  },
  { symbol: "hood.us",  yahoo: "HOOD",    name: "HOOD"  },
  { symbol: "mu.us",    yahoo: "MU",      name: "MU"    },
  { symbol: "brk-b.us", yahoo: "BRK-B",   name: "BRK-B" },
  { symbol: "rklb.us",  yahoo: "RKLB",    name: "RKLB"  },
  { symbol: "amzn.us",  yahoo: "AMZN",    name: "AMZN"  },
  { symbol: "ko.us",    yahoo: "KO",      name: "KO"    },
  { symbol: "zeta.us",  yahoo: "ZETA",    name: "ZETA"  },
  { symbol: "q.us",     yahoo: "Q",       name: "Q"     },
  { symbol: "sols.us",  yahoo: "SOLS",    name: "SOLS"  },
];

function friendlyNameForSymbol(symbol: string): string {
  const s = (symbol || "").trim();
  for (const item of DEFAULT_ITEMS) {
    if (item.symbol.toLowerCase() === s.toLowerCase()) return item.name;
  }
  if (s.toLowerCase().endsWith(".us")) return s.slice(0, -3).toUpperCase();
  return s.toUpperCase();
}

function toYahooSymbol(raw: string): string | null {
  if (!raw) return null;
  const s = raw.trim();
  for (const item of DEFAULT_ITEMS) {
    if (item.symbol.toLowerCase() === s.toLowerCase()) return item.yahoo;
  }
  if (s.toLowerCase().endsWith(".us")) return s.slice(0, -3).toUpperCase();
  return s.toUpperCase();
}

function normalizeStockSymbol(raw: string): string | null {
  let s = (raw || "").trim().toUpperCase().replace(/\s+/g, "");
  if (!s) return null;
  if (s.endsWith(".US")) s = s.slice(0, -3);
  s = s.replace(/\./g, "-");
  if (!/^[A-Z0-9-]+$/.test(s)) return null;
  return `${s}.US`;
}

// ── Market overview: fetch from Yahoo's chart API ────────────────────────────
async function buildMarketRow(
  symbol: string,
  yahooSym: string,
  displayName: string,
): Promise<Record<string, unknown> | null> {
  try {
    const points = await fetchYahooChart(yahooSym, "1y", "1d");
    if (!points.length) return null;
    const latest = points[points.length - 1];
    const close = latest.close;
    const asOf = latest.date;

    const w = points.length > 5  ? points[points.length - 6].close  : null;
    const m = points.length > 21 ? points[points.length - 22].close : null;
    const q = points.length > 63 ? points[points.length - 64].close : null;
    // 1Y % vs oldest bar in Yahoo's `range=1y` window (≈ 252 trading days).
    // Yahoo often returns 251 daily bars for US equities (^GSPC etc.), so a
    // threshold of 252 would permanently blank the 1Y column — `points[0]` is
    // always the window anchor for this fetch.
    const y = points.length >= 2 ? points[0].close : null;

    const pct = (prev: number | null) => prev ? Math.round((close / prev - 1) * 10000) / 100 : null;
    return {
      symbol, name: displayName, as_of: asOf, close,
      chg_1w_pct: pct(w), chg_1m_pct: pct(m),
      chg_3m_pct: pct(q), chg_1y_pct: pct(y),
      source_url: `https://finance.yahoo.com/quote/${encodeURIComponent(yahooSym)}`,
    };
  } catch {
    return null;
  }
}

// ── Main fetch handler ────────────────────────────────────────────────────────
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const { pathname } = url;

    // OPTIONS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    // ── /api/latest ──────────────────────────────────────────────────────────
    if (pathname === "/api/latest" && request.method === "GET") {
      const latest = await getLatestObservations(env.DB);
      const signals = computeSignals(latest);
      const signalMap = Object.fromEntries(signals.map((s) => [s.indicator_id, s]));
      const lastUpdate = await getLastUpdateTime(env.DB);

      const rows = ALL_INDICATOR_IDS.map((id) => {
        const o = latest[id];
        const s = signalMap[id];
        const name = s?.title ?? INDICATOR_NAMES[id] ?? id;

        let valueDisplay: string | null = null;
        if (o) {
          const v = o.value;
          if (id === "us_high_yield_spread") {
            const bp = (o.unit === "bp" || v > 30) ? v : v * 100;
            valueDisplay = (bp / 100).toFixed(2);
          } else if (id === "yc_10y_2y") {
            valueDisplay = (v >= 0 ? "+" : "") + v.toFixed(2);
          } else {
            valueDisplay = v.toFixed(2);
          }
        }

        let unitDisplay = o?.unit ?? null;
        if (id === "us_high_yield_spread" && unitDisplay === "bp") unitDisplay = "%";
        if (unitDisplay === "percent") unitDisplay = "%";

        return {
          id, name,
          as_of: o?.as_of ? o.as_of.slice(5) : null,  // "MM-DD"
          value: valueDisplay,
          unit: unitDisplay,
          source: o?.source ?? null,
          source_url: INDICATOR_SOURCE_URLS[id] ?? null,
          is_top: s?.top ?? false,
          is_bottom: s?.bottom ?? false,
        };
      });

      return json({ rows, last_update: lastUpdate });
    }

    // ── /api/alerts ──────────────────────────────────────────────────────────
    if (pathname === "/api/alerts" && request.method === "GET") {
      const latest = await getLatestObservations(env.DB);
      const signals = computeSignals(latest);
      return json(signals);
    }

    // ── /api/regime ──────────────────────────────────────────────────────────
    if (pathname === "/api/regime" && request.method === "GET") {
      const latest = await getLatestObservations(env.DB);
      const ycHistory = await getRecentObservations(env.DB, "yc_10y_2y", 720);
      const ycRecentlyInverted = ycHistory.some((o) => o.value < 0);
      const regime = computeMarketRegime(latest, ycRecentlyInverted);
      return json(regime);
    }

    // ── /api/indicator-history ───────────────────────────────────────────────
    if (pathname === "/api/indicator-history" && request.method === "GET") {
      const indicatorId = url.searchParams.get("indicator_id") ?? "";
      const days = Math.max(1, Math.min(parseInt(url.searchParams.get("days") ?? "3650"), 36500));

      if (!ALL_INDICATOR_IDS.includes(indicatorId as typeof ALL_INDICATOR_IDS[number])) {
        return err("Unknown indicator_id", 404);
      }

      const obs = await getRecentObservations(env.DB, indicatorId, days);
      const series = obs.map((o) => {
        let v = o.value;
        let unit = o.unit;
        if (indicatorId === "us_high_yield_spread" && unit === "bp") {
          v = v / 100;
          unit = "%";
        } else if (unit === "percent") { unit = "%"; }
        else if (["0-100", "index", "ratio"].includes(unit)) { unit = ""; }
        return { date: o.as_of, value: v };
      });

      const th = INDICATOR_THRESHOLDS[indicatorId] ?? {};
      return json({ indicator_id: indicatorId, unit: series[0] ? obs[0]?.unit : null, series, ...th });
    }

    // ── /api/market-overview ─────────────────────────────────────────────────
    if (pathname === "/api/market-overview" && request.method === "GET") {
      const rawSymbols = url.searchParams.get("symbols") ?? "";
      const extraSymbols = rawSymbols.split(",").map((s) => s.trim()).filter(Boolean);
      const force = url.searchParams.get("refresh") === "1";

      // Build the list of symbols to fetch. Each entry is
      // [symbolKey, yahooSym, displayName].
      const symbolPlan = new Map<string, { yahoo: string; name: string }>();
      for (const item of DEFAULT_ITEMS) {
        symbolPlan.set(item.symbol, { yahoo: item.yahoo, name: item.name });
      }
      for (const raw of extraSymbols) {
        const norm = normalizeStockSymbol(raw);
        if (norm) {
          const yahoo = norm.slice(0, -3);
          symbolPlan.set(norm.toLowerCase(), { yahoo, name: yahoo });
        }
      }

      // Try cache from D1 first (unless force refresh)
      let dbRows: Record<string, unknown>[] = [];
      if (!force) {
        const syms = [...symbolPlan.keys()];
        dbRows = await getMarketOverviewRows(env.DB, syms);
      }

      const dbMap = new Map<string, Record<string, unknown>>();
      for (const r of dbRows) dbMap.set(String(r.symbol).toLowerCase(), r);

      // Fetch missing symbols from Yahoo (async, best-effort)
      const missingSymbols = [...symbolPlan.entries()].filter(([sym]) => !dbMap.has(sym));
      if (missingSymbols.length > 0) {
        const fetched = await Promise.allSettled(
          missingSymbols.map(([sym, plan]) => buildMarketRow(sym, plan.yahoo, plan.name)),
        );
        const newRows: Record<string, unknown>[] = [];
        for (const r of fetched) {
          if (r.status === "fulfilled" && r.value) {
            newRows.push(r.value);
            dbMap.set(String(r.value.symbol).toLowerCase(), r.value);
          }
        }
        if (newRows.length) {
          // Cloudflare Workers terminate in-flight async work once the
          // Response is returned unless it's wrapped in ctx.waitUntil.
          // Using `void` here silently dropped the D1 write, which is why
          // the Market page would "flash fresh" on Reload and then revert
          // to the old values after a browser refresh.
          ctx.waitUntil(upsertMarketOverviewRows(env.DB, newRows));
        }
      }

      // Backfill: make sure cached rows always carry the friendly display
      // name. Older D1 rows were written with the Yahoo slug (^GSPC, GC=F,
      // BTC-USD, ...) as `name`, so a page load can now heal them in-place.
      for (const [sym, plan] of symbolPlan.entries()) {
        const row = dbMap.get(sym);
        if (!row) continue;
        const desired = plan.name;
        if (row.name !== desired) {
          row.name = desired;
        }
      }

      // Build ordered result
      const rows = [...symbolPlan.keys()].map((sym) => dbMap.get(sym)).filter(Boolean);
      return json({ rows, as_of_utc: new Date().toISOString(), refreshing: false });
    }

    // ── /api/stock-detail ────────────────────────────────────────────────────
    if (pathname === "/api/stock-detail" && request.method === "GET") {
      const symbol = url.searchParams.get("symbol") ?? "";
      const range = url.searchParams.get("range") ?? "1y";
      const validRanges = ["1mo", "3mo", "6mo", "1y", "2y", "5y"];
      const rng = validRanges.includes(range) ? range : "1y";

      const yahooSym = toYahooSymbol(symbol);
      if (!yahooSym) return err("Unknown symbol", 404);

      const points = await fetchYahooChart(yahooSym, rng, "1d");
      const series = points.map((p) => ({ date: p.date, close: p.close }));
      const latestClose = series.length ? series[series.length - 1].close : null;
      const firstClose = series.length > 1 ? series[0].close : null;
      const chgPct = latestClose && firstClose ? Math.round((latestClose / firstClose - 1) * 10000) / 100 : null;

      let articles: unknown[] = [];
      const newsTicker = newsTickerForYahooSymbol(yahooSym);
      const newsEnabled = Boolean(env.FINNHUB_KEY);
      if (newsEnabled && newsTicker) {
        const todayStr = new Date().toISOString().slice(0, 10);
        const fromStr = new Date(Date.now() - 30 * 86400 * 1000).toISOString().slice(0, 10);
        const cached = await getNewsCacheEntry(env.DB, `stock:${newsTicker}`, todayStr, 3600);
        if (cached) {
          articles = cached;
        } else {
          articles = await fetchCompanyNews(newsTicker, fromStr, todayStr, env.FINNHUB_KEY!);
          ctx.waitUntil(upsertNewsCache(env.DB, `stock:${newsTicker}`, todayStr, articles));
        }
      }

      return json({ symbol, yahoo: yahooSym, range: rng, latest_close: latestClose, chg_pct: chgPct, series, news: articles, news_enabled: newsEnabled, has_news: Boolean(newsTicker) });
    }

    // ── /api/world-indices ───────────────────────────────────────────────────
    if (pathname === "/api/world-indices" && request.method === "GET") {
      const newsEnabled = Boolean(env.FINNHUB_KEY);
      const todayStr = new Date().toISOString().slice(0, 10);

      const rows = await Promise.allSettled(
        WORLD_INDICES.map(async (meta) => {
          const points = await fetchYahooChart(meta.yahoo, "5d", "1d");
          if (!points.length) return null;
          const last = points[points.length - 1];
          const prev = points.length > 1 ? points[points.length - 2] : null;
          const chg1d = prev ? Math.round((last.close / prev.close - 1) * 10000) / 100 : null;

          let news: unknown[] = [];
          if (newsEnabled && meta.finnhub) {
            const cacheKey = `world:${meta.stooq}`;
            const cached = await getNewsCacheEntry(env.DB, cacheKey, todayStr, 3600);
            if (cached) {
              news = cached;
            } else {
              const from = new Date(Date.now() - 3 * 86400 * 1000).toISOString().slice(0, 10);
              news = await fetchCompanyNews(meta.finnhub, from, todayStr, env.FINNHUB_KEY!);
              ctx.waitUntil(upsertNewsCache(env.DB, cacheKey, todayStr, news));
            }
          }

          return {
            stooq: meta.stooq, yahoo: meta.yahoo, name: meta.name,
            country: meta.country, iso: meta.iso, lat: meta.lat, lng: meta.lng,
            close: last.close, as_of: last.date, chg_1d_pct: chg1d,
            ok: true, is_sample: false, news, headlines: news,
          };
        }),
      );

      const resultRows = rows.map((r, i) => {
        if (r.status === "fulfilled" && r.value) return r.value;
        const meta = WORLD_INDICES[i];
        return { stooq: meta.stooq, name: meta.name, country: meta.country, iso: meta.iso, lat: meta.lat, lng: meta.lng, ok: false, is_sample: true, close: null, chg_1d_pct: null, news: [], headlines: [] };
      });

      return json({
        rows: resultRows,
        as_of_utc: new Date().toISOString(),
        refreshing: false,
        news_enabled: newsEnabled,
        real_count: resultRows.filter((r) => r.ok && !r.is_sample).length,
        sample_count: resultRows.filter((r) => r.ok && r.is_sample).length,
        total: WORLD_INDICES.length,
        indices_meta: WORLD_INDICES.map((m) => ({ stooq: m.stooq, name: m.name, country: m.country, iso: m.iso })),
      });
    }

    // ── /api/index-history ───────────────────────────────────────────────────
    if (pathname === "/api/index-history" && request.method === "GET") {
      const symbol = url.searchParams.get("symbol") ?? "";
      const rangeKey = url.searchParams.get("range") ?? "1y";
      const meta = getIndexMeta(symbol);
      if (!meta) return err(`Unknown symbol ${symbol}`, 404);

      const yahooRange: Record<string, string> = {
        "1m":  "1mo",
        "3m":  "3mo",
        "6m":  "6mo",
        "1y":  "1y",
        "2y":  "2y",
        "5y":  "5y",
        "all": "max",
      };
      const points = await fetchYahooChart(meta.yahoo, yahooRange[rangeKey] ?? "1y", "1d");

      // Build series with chg_pct (daily % change)
      const series: Array<{ date: string; close: number; chg_pct: number | null }> = [];
      for (let i = 0; i < points.length; i++) {
        const chg = i > 0 ? Math.round((points[i].close / points[i - 1].close - 1) * 10000) / 100 : null;
        series.push({ date: points[i].date, close: points[i].close, chg_pct: chg });
      }

      // Compute significant moves (top 6 by |chg_pct|, gated by 1.5 * stdev)
      const significant: Array<{ date: string; close: number; chg_pct: number; news: unknown[] }> = [];
      if (series.length >= 5) {
        const valid = series
          .map((p, i) => ({ i, abs: p.chg_pct != null ? Math.abs(p.chg_pct) : -1 }))
          .filter((v) => v.abs >= 0);
        valid.sort((a, b) => b.abs - a.abs);
        const topNIdx = new Set(valid.slice(0, 6).map((v) => v.i));

        const vals = valid.map((v) => v.abs);
        const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
        const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / Math.max(1, vals.length - 1);
        const sd = Math.sqrt(variance);
        const gate = Math.max(1.5, 1.5 * sd);

        let chosenIdx = series
          .map((p, i) => i)
          .filter((i) => topNIdx.has(i) && series[i].chg_pct != null && Math.abs(series[i].chg_pct!) >= gate);

        if (!chosenIdx.length) {
          chosenIdx = valid.slice(0, 3).map((v) => v.i);
        }
        chosenIdx.sort((a, b) => a - b);
        chosenIdx = chosenIdx.slice(0, 8);

        // Fetch news for significant dates if FINNHUB_KEY is set
        const newsEnabled = Boolean(env.FINNHUB_KEY);
        const todayStr = new Date().toISOString().slice(0, 10);
        for (const i of chosenIdx) {
          const p = series[i];
          let dayNews: unknown[] = [];
          if (newsEnabled && meta.finnhub) {
            const dateStr = p.date;
            const cacheKey = `idx-news:${meta.stooq}:${dateStr}`;
            const cached = await getNewsCacheEntry(env.DB, cacheKey, dateStr, 86400);
            if (cached) {
              dayNews = cached;
            } else {
              const from = new Date(new Date(dateStr).getTime() - 1 * 86400 * 1000).toISOString().slice(0, 10);
              const to = new Date(new Date(dateStr).getTime() + 1 * 86400 * 1000).toISOString().slice(0, 10);
              dayNews = await fetchCompanyNews(meta.finnhub, from, to, env.FINNHUB_KEY!);
              dayNews = (dayNews as unknown[]).slice(0, 3);
              ctx.waitUntil(upsertNewsCache(env.DB, cacheKey, dateStr, dayNews));
            }
          }
          significant.push({ date: p.date, close: p.close, chg_pct: p.chg_pct!, news: dayNews });
        }
      }

      return json({
        stooq: meta.stooq, name: meta.name, country: meta.country, range: rangeKey,
        series, significant,
        is_sample: false,
        news_enabled: Boolean(env.FINNHUB_KEY),
      });
    }

    // ── /api/index-news ──────────────────────────────────────────────────────
    if (pathname === "/api/index-news" && request.method === "GET") {
      const symbol = url.searchParams.get("symbol") ?? "";
      const dateStr = url.searchParams.get("date") ?? new Date().toISOString().slice(0, 10);
      const limit = Math.max(1, Math.min(parseInt(url.searchParams.get("limit") ?? "5"), 20));
      const meta = getIndexMeta(symbol);

      if (!meta) return err(`Unknown symbol ${symbol}`, 404);
      const newsEnabled = Boolean(env.FINNHUB_KEY);
      if (!newsEnabled || !meta.finnhub) {
        return json({ articles: [], symbol, date: dateStr, news_enabled: newsEnabled });
      }

      const cached = await getNewsCacheEntry(env.DB, `world:${meta.stooq}`, dateStr, 86400);
      if (cached) return json({ articles: (cached as unknown[]).slice(0, limit), symbol, date: dateStr, news_enabled: true });

      const from = new Date(new Date(dateStr).getTime() - 3 * 86400 * 1000).toISOString().slice(0, 10);
      const articles = await fetchCompanyNews(meta.finnhub, from, dateStr, env.FINNHUB_KEY!);
      ctx.waitUntil(upsertNewsCache(env.DB, `world:${meta.stooq}`, dateStr, articles));

      return json({ articles: articles.slice(0, limit), symbol, date: dateStr, news_enabled: true });
    }

    // ── /api/refresh (manual trigger, rate-limited per IP: 1 per 5 min) ────
    if (pathname === "/api/refresh" && request.method === "POST") {
      const clientIp = request.headers.get("CF-Connecting-IP") || "unknown";
      const rlKey = `ratelimit:refresh:${clientIp}`;
      const COOLDOWN_SECONDS = 5 * 60;

      const prev = await env.DB.prepare(
        "SELECT value FROM kv_store WHERE key = ?"
      ).bind(rlKey).first<{ value: string }>();
      if (prev) {
        const lastTs = parseInt(prev.value, 10) || 0;
        const elapsed = Math.floor(Date.now() / 1000) - lastTs;
        if (elapsed < COOLDOWN_SECONDS) {
          const wait = COOLDOWN_SECONDS - elapsed;
          const h = Math.floor(wait / 3600);
          const m = Math.ceil((wait % 3600) / 60);
          return err(`Rate limited. Try again in ${h}h ${m}m.`, 429);
        }
      }

      const nowTs = String(Math.floor(Date.now() / 1000));
      await env.DB.prepare(
        "INSERT INTO kv_store (key, value, updated_at) VALUES (?, ?, datetime('now')) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at"
      ).bind(rlKey, nowTs).run();

      let refreshOk: boolean | string[] = false;
      let errors: string[] = [];
      let wrote = 0;
      try {
        const r = await fetchAllProviders(env);
        refreshOk = r.ok;
        errors = r.err;
        await upsertObservations(env.DB, r.observations);
        wrote = r.observations.length;
      } catch (e) {
        console.error("/api/refresh: fetchAllProviders/upsert failed", e);
        errors = [...errors, String(e)];
      }

      // Also refresh the market_overview cache so the header "Update"
      // button brings Indices / Futures & Crypto / default Stocks
      // forward in addition to the macro indicators.
      let marketWrote = 0;
      try {
        const settled = await Promise.allSettled(
          DEFAULT_ITEMS.map((item) =>
            buildMarketRow(item.symbol, item.yahoo, item.name),
          ),
        );
        const freshRows: Record<string, unknown>[] = [];
        for (const r of settled) {
          if (r.status === "fulfilled" && r.value) freshRows.push(r.value);
        }
        if (freshRows.length) {
          await upsertMarketOverviewRows(env.DB, freshRows);
          marketWrote = freshRows.length;
        }
      } catch (e) {
        console.error("/api/refresh: market_overview refresh failed", e);
        errors = [...errors, `market_overview: ${String(e)}`];
      }

      // Always advance the heartbeat so the UI's "Last Updated" stamp
      // moves even if upstream sources errored.
      try { await setLastCronRun(env.DB); } catch (e) {
        console.error("/api/refresh: setLastCronRun failed", e);
      }
      return json({ ok: refreshOk, err: errors, wrote, market_wrote: marketWrote });
    }

    // ── /api/status ──────────────────────────────────────────────────────────
    if (pathname === "/api/status" && request.method === "GET") {
      const lastUpdate = await getLastUpdateTime(env.DB);
      return json({
        ok: true,
        last_update: lastUpdate,
        news_enabled: Boolean(env.FINNHUB_KEY),
        fred_enabled: Boolean(env.FRED_API_KEY),
      });
    }

    return err("Not found", 404);
  },

  // ── Cron Trigger ─────────────────────────────────────────────────────────
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(
      (async () => {
        const t0 = Date.now();
        console.log(`scheduled: tick @ ${new Date().toISOString()}`);

        // 1) Write the heartbeat FIRST. Earlier this lived at the bottom,
        //    so any wall-time/CPU overrun in the upstream fetches would
        //    silently drop the heartbeat write and the dashboard's
        //    "Last Updated" timestamp would never move on a tick that
        //    timed out. Doing it first means the timestamp tracks the
        //    cron schedule itself, not the success of every scraper.
        try {
          await setLastCronRun(env.DB);
          console.log(`scheduled: heartbeat written (+${Date.now() - t0}ms)`);
        } catch (e) {
          console.error("scheduled: setLastCronRun (early) failed", e);
        }

        // 2) Pull every macro provider into D1 (best-effort).
        try {
          const { ok, err, observations } = await fetchAllProviders(env);
          await upsertObservations(env.DB, observations);
          console.log(
            `scheduled: providers ok=${ok.length} err=${err.length} ` +
              `wrote=${observations.length} (+${Date.now() - t0}ms)`,
          );
          if (err.length) console.error("scheduled: provider errors:", err);
        } catch (e) {
          console.error("scheduled: fetchAllProviders/upsert failed", e);
        }

        // 3) Refresh the market_overview cache (Indices / Futures & Crypto
        //    / Stocks). Without this, /api/market-overview keeps returning
        //    the first-ever snapshot — the endpoint only re-fetches *missing*
        //    symbols, so rows never age forward until a user hits Reload.
        try {
          const rows = await Promise.allSettled(
            DEFAULT_ITEMS.map((item) =>
              buildMarketRow(item.symbol, item.yahoo, item.name),
            ),
          );
          const fresh: Record<string, unknown>[] = [];
          for (const r of rows) {
            if (r.status === "fulfilled" && r.value) fresh.push(r.value);
          }
          if (fresh.length) await upsertMarketOverviewRows(env.DB, fresh);
          console.log(
            `scheduled: market_overview wrote=${fresh.length} ` +
              `(+${Date.now() - t0}ms)`,
          );
        } catch (e) {
          console.error("scheduled: market_overview refresh failed", e);
        }

        // 4) Final heartbeat. Most ticks reach here; this updates the
        //    timestamp to the actual *completion* time so the dashboard
        //    "Last Updated" reflects when the latest data really landed.
        try {
          await setLastCronRun(env.DB);
        } catch (e) {
          console.error("scheduled: setLastCronRun (final) failed", e);
        }

        console.log(`scheduled: done in ${Date.now() - t0}ms`);
      })(),
    );
  },
} satisfies ExportedHandler<Env>;
