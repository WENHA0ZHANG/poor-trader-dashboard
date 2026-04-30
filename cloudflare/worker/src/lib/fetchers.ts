/**
 * Cron data fetchers — each function pulls one data source and returns
 * a list of Observation objects ready to be upserted into D1.
 *
 * These run on the Cron Trigger schedule (every 4 hours by default).
 * Scrapers that require browser-level JS (YCharts, Multpl, CNN F&G page)
 * cannot run in Workers — for those we rely on D1 data seeded from the
 * existing Python backend or manual updates.
 */
import type { Observation } from "./types";
import { fetchYahooChart } from "./yahoo.ts";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── FRED API ────────────────────────────────────────────────────────────────
// FRED series IDs:
//   BAMLH0A0HYM2  = US HY OAS (bp)
//   T10Y2Y        = 10Y-2Y Treasury yield curve (%)
//   CBOE/SKEW     = CBOE SKEW index (via FRED)

async function fetchFredSeries(
  seriesId: string,
  fredApiKey: string,
  limit = 10,
): Promise<Array<{ date: string; value: string }>> {
  const url = new URL("https://api.stlouisfed.org/fred/series/observations");
  url.searchParams.set("series_id", seriesId);
  url.searchParams.set("api_key", fredApiKey);
  url.searchParams.set("file_type", "json");
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("sort_order", "desc");

  const resp = await fetch(url.toString(), { signal: AbortSignal.timeout(10000) });
  if (!resp.ok) return [];
  const data = await resp.json() as { observations?: Array<{ date: string; value: string }> };
  return data.observations ?? [];
}

export async function fetchHyOas(fredApiKey: string): Promise<Observation[]> {
  const rows = await fetchFredSeries("BAMLH0A0HYM2", fredApiKey);
  const out: Observation[] = [];
  for (const row of rows) {
    if (!row.date || row.value === "." || !row.value) continue;
    const val = parseFloat(row.value);
    if (isNaN(val)) continue;
    out.push({
      indicator_id: "us_high_yield_spread",
      as_of: row.date,
      value: val * 100,  // FRED gives % → store as bp to match existing convention
      unit: "bp",
      source: "FRED:BAMLH0A0HYM2",
      meta_json: null,
      inserted_at: today(),
    });
  }
  return out;
}

export async function fetchYieldCurve(fredApiKey: string): Promise<Observation[]> {
  const rows = await fetchFredSeries("T10Y2Y", fredApiKey);
  const out: Observation[] = [];
  for (const row of rows) {
    if (!row.date || row.value === "." || !row.value) continue;
    const val = parseFloat(row.value);
    if (isNaN(val)) continue;
    out.push({
      indicator_id: "yc_10y_2y",
      as_of: row.date,
      value: val,
      unit: "percent",
      source: "FRED:T10Y2Y",
      meta_json: null,
      inserted_at: today(),
    });
  }
  return out;
}

// ── VIX from Yahoo Finance ──────────────────────────────────────────────────
export async function fetchVix(): Promise<Observation[]> {
  const points = await fetchYahooChart("^VIX", "5d", "1d");
  const out: Observation[] = [];
  for (const p of points.slice(-3)) {
    out.push({
      indicator_id: "vix",
      as_of: p.date,
      value: p.close,
      unit: "index",
      source: "Yahoo:^VIX",
      meta_json: null,
      inserted_at: today(),
    });
  }
  return out;
}

// ── S&P 500 RSI from Yahoo Finance ──────────────────────────────────────────
// Wilder's smoothed RSI: seed with simple averages over the first `period`
// daily up/down moves, then apply Wilder smoothing for every later point.
// Matches TradingView / StockCharts / Yahoo "RSI(14)" convention.
function computeRsi(closes: number[], period = 14): number | null {
  if (closes.length < period + 1) return null;

  let gainSum = 0, lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gainSum += diff;
    else lossSum -= diff;
  }
  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;

  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
  }

  if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
  const rs = avgGain / avgLoss;
  return Math.round((100 - 100 / (1 + rs)) * 100) / 100;
}

export async function fetchSp500Rsi(): Promise<Observation[]> {
  // Fetch 1y so Wilder smoothing has plenty of history to converge to the
  // standard "RSI(14)" value reported on Yahoo / TradingView.
  const points = await fetchYahooChart("^GSPC", "1y", "1d");
  if (points.length < 30) return [];
  const closes = points.map((p) => p.close);
  const rsi = computeRsi(closes, 14);
  if (rsi == null) return [];
  return [{
    indicator_id: "sp500_rsi",
    as_of: points[points.length - 1].date,
    value: rsi,
    unit: "0-100",
    source: "Yahoo:^GSPC/RSI14",
    meta_json: null,
    inserted_at: today(),
  }];
}

// ── CBOE SKEW from Yahoo Finance ─────────────────────────────────────────────
export async function fetchCboeSkew(): Promise<Observation[]> {
  const points = await fetchYahooChart("^SKEW", "5d", "1d");
  const out: Observation[] = [];
  for (const p of points.slice(-3)) {
    out.push({
      indicator_id: "cboe_skew",
      as_of: p.date,
      value: p.close,
      unit: "index",
      source: "Yahoo:^SKEW",
      meta_json: null,
      inserted_at: today(),
    });
  }
  return out;
}

// ── CNN Fear & Greed (public JSON endpoint) ──────────────────────────────────
interface CnnFgData {
  fear_and_greed?: { score?: number; rating?: string; timestamp?: string };
  put_call_options?: { score?: number; timestamp?: string };
}

export async function fetchCnnFearGreed(): Promise<Observation[]> {
  try {
    const resp = await fetch(
      "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
      { headers: { "User-Agent": "Mozilla/5.0" }, signal: AbortSignal.timeout(8000) },
    );
    if (!resp.ok) return [];
    const data = await resp.json() as CnnFgData;
    const fg = data?.fear_and_greed;
    if (!fg?.score) return [];

    const asOf = fg.timestamp
      ? new Date(fg.timestamp).toISOString().slice(0, 10)
      : today();
    const out: Observation[] = [{
      indicator_id: "cnn_fear_greed_index",
      as_of: asOf,
      value: fg.score,
      unit: "0-100",
      source: "CNN:dataviz",
      meta_json: JSON.stringify({ rating: fg.rating ?? null }),
      inserted_at: today(),
    }];

    const pc = data?.put_call_options;
    if (pc?.score) {
      out.push({
        indicator_id: "cnn_put_call_options",
        as_of: pc.timestamp ? new Date(pc.timestamp).toISOString().slice(0, 10) : asOf,
        value: pc.score,
        unit: "ratio",
        source: "CNN:dataviz",
        meta_json: null,
        inserted_at: today(),
      });
    }
    return out;
  } catch {
    return [];
  }
}

// ── Run all fetchable providers ──────────────────────────────────────────────
export async function fetchAllProviders(env: {
  FRED_API_KEY?: string;
}): Promise<{ ok: string[]; err: string[]; observations: Observation[] }> {
  const ok: string[] = [];
  const err: string[] = [];
  const observations: Observation[] = [];

  const tasks: Array<[string, () => Promise<Observation[]>]> = [
    ["cnn", fetchCnnFearGreed],
    ["vix", fetchVix],
    ["sp500_rsi", fetchSp500Rsi],
    ["cboe_skew", fetchCboeSkew],
  ];

  if (env.FRED_API_KEY) {
    tasks.push(["hy_oas", () => fetchHyOas(env.FRED_API_KEY!)]);
    tasks.push(["yc_10y2y", () => fetchYieldCurve(env.FRED_API_KEY!)]);
  }

  for (const [name, fn] of tasks) {
    try {
      const obs = await fn();
      observations.push(...obs);
      ok.push(`${name}: ${obs.length} records`);
    } catch (e) {
      err.push(`${name}: ${String(e)}`);
    }
  }

  return { ok, err, observations };
}
