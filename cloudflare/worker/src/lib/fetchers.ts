/**
 * Cron data fetchers — each function pulls one data source and returns
 * a list of Observation objects ready to be upserted into D1.
 *
 * These run on the hourly cron trigger. Providers that require a real
 * browser (Barron's is a Next.js shell, the CNN F&G *page* is JS-rendered)
 * fall back to simpler HTML/API sources that work from a Worker.
 */
import type { Observation } from "./types";
import { fetchYahooChart } from "./yahoo.ts";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

// Shared browser-ish headers used by every scraper that hits a publicly
// cached HTML/JSON endpoint. Minimal UAs now get filtered (CNN → 418,
// several ad-tech edges → 403) so we mimic a desktop Chrome.
const BROWSER_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) " +
  "Chrome/131.0.0.0 Safari/537.36";

const HTML_HEADERS: Record<string, string> = {
  "User-Agent": BROWSER_UA,
  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  "Accept-Language": "en-US,en;q=0.9",
};

/** Best-effort HTML fetch. Returns empty string on any failure so callers
 *  can no-op instead of crashing the whole scheduled run. */
async function fetchHtml(
  url: string,
  referer?: string,
  timeoutMs = 15000,
): Promise<string> {
  try {
    const headers: Record<string, string> = { ...HTML_HEADERS };
    if (referer) headers["Referer"] = referer;
    const resp = await fetch(url, {
      headers,
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!resp.ok) {
      console.error(`fetchHtml: ${url} returned ${resp.status}`);
      return "";
    }
    return await resp.text();
  } catch (e) {
    console.error(`fetchHtml: ${url} threw`, e);
    return "";
  }
}

// ── FRED fetcher (with proxy fallback) ──────────────────────────────────────
// Cloudflare Workers' fetch proxy consistently returns HTTP 520 when hitting
// either `api.stlouisfed.org` OR `fred.stlouisfed.org` directly (verified via
// `wrangler tail`). This appears to be a TLS/handshake edge case between CF
// Workers and the St. Louis Fed's stack. Going through a public CORS proxy
// (`api.allorigins.win`) reaches FRED fine and has been stable for years,
// so we use it as the primary path, with direct FRED attempts as fallback
// for the day CF's routing starts working again.
const ALLORIGINS_BASE = "https://api.allorigins.win/raw?url=";

async function _fetchText(
  url: string,
  accept: string,
  timeoutMs = 20000,
): Promise<string | null> {
  try {
    const resp = await fetch(url, {
      headers: { "User-Agent": BROWSER_UA, Accept: accept },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!resp.ok) return null;
    return await resp.text();
  } catch {
    return null;
  }
}

/** Fetch a FRED series as an array of {date,value} rows, newest-first.
 *  Tries: allorigins-proxied CSV → direct JSON API (if keyed) → direct CSV. */
async function fetchFredSeries(
  seriesId: string,
  fredApiKey: string | undefined,
  sinceDays = 90,
): Promise<Array<{ date: string; value: string }>> {
  const cosd = new Date(Date.now() - sinceDays * 86400 * 1000)
    .toISOString()
    .slice(0, 10);
  const csvPath =
    `https://fred.stlouisfed.org/graph/fredgraph.csv?id=${encodeURIComponent(seriesId)}&cosd=${cosd}`;

  const parseCsv = (text: string): Array<{ date: string; value: string }> => {
    const lines = text.trim().split(/\r?\n/);
    const out: Array<{ date: string; value: string }> = [];
    for (let i = lines[0]?.toLowerCase().includes("date") ? 1 : 0; i < lines.length; i++) {
      const parts = lines[i].split(",");
      if (parts.length < 2) continue;
      out.push({ date: parts[0].trim(), value: parts[1].trim() });
    }
    return out.reverse();   // CSV is oldest-first; callers expect newest-first
  };

  // 1) Primary: allorigins-proxied CSV. No key, bypasses CF↔FRED TLS quirk.
  const proxied = await _fetchText(
    ALLORIGINS_BASE + encodeURIComponent(csvPath),
    "text/csv,text/plain",
  );
  if (proxied && proxied.includes(",")) {
    const rows = parseCsv(proxied);
    if (rows.length) return rows;
  }
  console.error(`fetchFredSeries(${seriesId}): proxy miss, trying direct API`);

  // 2) Fallback: direct JSON API if key present.
  if (fredApiKey) {
    const apiUrl = new URL("https://api.stlouisfed.org/fred/series/observations");
    apiUrl.searchParams.set("series_id", seriesId);
    apiUrl.searchParams.set("api_key", fredApiKey);
    apiUrl.searchParams.set("file_type", "json");
    apiUrl.searchParams.set("limit", "15");
    apiUrl.searchParams.set("sort_order", "desc");
    try {
      const resp = await fetch(apiUrl.toString(), {
        headers: { "User-Agent": BROWSER_UA, Accept: "application/json" },
        signal: AbortSignal.timeout(20000),
      });
      if (resp.ok) {
        const data = (await resp.json()) as {
          observations?: Array<{ date: string; value: string }>;
        };
        if (data.observations?.length) return data.observations;
      } else {
        console.error(`fetchFredSeries(${seriesId}): direct JSON HTTP ${resp.status}`);
      }
    } catch (e) {
      console.error(`fetchFredSeries(${seriesId}): direct JSON threw`, e);
    }
  }

  // 3) Last resort: direct CSV (usually also 520, but try anyway).
  const direct = await _fetchText(csvPath, "text/csv");
  if (direct && direct.includes(",")) {
    return parseCsv(direct);
  }
  return [];
}

function toFredObservations(
  rows: Array<{ date: string; value: string }>,
  indicatorId: string,
  unit: string,
  source: string,
  mult = 1,
): Observation[] {
  const out: Observation[] = [];
  for (const row of rows) {
    if (!row.date || row.value === "." || !row.value) continue;
    const val = parseFloat(row.value);
    if (isNaN(val)) continue;
    out.push({
      indicator_id: indicatorId,
      as_of: row.date,
      value: val * mult,
      unit,
      source,
      meta_json: null,
      inserted_at: today(),
    });
  }
  return out;
}

export async function fetchHyOas(fredApiKey?: string): Promise<Observation[]> {
  const rows = await fetchFredSeries("BAMLH0A0HYM2", fredApiKey);
  // FRED gives %, D1 stores bp to match the existing historical convention.
  return toFredObservations(rows, "us_high_yield_spread", "bp", "FRED:BAMLH0A0HYM2", 100);
}

export async function fetchYieldCurve(fredApiKey?: string): Promise<Observation[]> {
  const rows = await fetchFredSeries("T10Y2Y", fredApiKey);
  return toFredObservations(rows, "yc_10y_2y", "percent", "FRED:T10Y2Y", 1);
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
// CNN actively rejects requests that don't look browser-like. A minimal
// "Mozilla/5.0" UA now gets a 418 "I'm a teapot. You're a bot." response
// — that's why F&G / Put-Call silently stopped updating on the deployed
// worker. The headers below mirror the ones the Python `CnnFearGreedProvider`
// uses and consistently get a 200 back.
const CNN_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
    "AppleWebKit/537.36 (KHTML, like Gecko) " +
    "Chrome/131.0.0.0 Safari/537.36",
  "Accept": "application/json, text/plain, */*",
  "Accept-Language": "en-US,en;q=0.9",
  "Referer": "https://edition.cnn.com/markets/fear-and-greed",
  "Origin": "https://edition.cnn.com",
};

interface CnnFgPoint { x?: number; y?: number; rating?: string }
interface CnnFgComponent {
  score?: number;
  rating?: string;
  timestamp?: number | string;
  data?: CnnFgPoint[];
}
interface CnnFgData {
  fear_and_greed?: CnnFgComponent;
  fear_and_greed_historical?: CnnFgComponent;
  put_call_options?: CnnFgComponent;
}

/** Parse CNN's mixed-type timestamp (ISO string OR ms-epoch number). */
function cnnTsToIsoDate(ts: number | string | undefined): string | null {
  if (ts === undefined || ts === null || ts === "") return null;
  try {
    const d = typeof ts === "number" ? new Date(ts) : new Date(String(ts));
    if (isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}

/** De-dupe by date, keeping the last occurrence (CNN duplicates the latest
 *  day as a placeholder — we prefer the most recent value). */
function dedupeByDate<T extends { as_of: string }>(rows: T[]): T[] {
  const map = new Map<string, T>();
  for (const r of rows) map.set(r.as_of, r);
  return [...map.values()];
}

export async function fetchCnnFearGreed(): Promise<Observation[]> {
  const resp = await fetch(
    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
    { headers: CNN_HEADERS, signal: AbortSignal.timeout(12000) },
  );
  if (!resp.ok) {
    console.error(
      `fetchCnnFearGreed: CNN returned ${resp.status} ${resp.statusText}`,
    );
    return [];
  }
  const data = (await resp.json()) as CnnFgData;

  const out: Observation[] = [];
  const insertedAt = today();

  // ── Fear & Greed Index ────────────────────────────────────────────────
  // Upsert the most recent ~60 days of history from fear_and_greed_historical
  // so chart views stay fresh across weekend gaps. Fall back to the scalar
  // `fear_and_greed` block when the historical array is missing.
  const fgHist = data?.fear_and_greed_historical?.data;
  const fgRows: Observation[] = [];
  if (Array.isArray(fgHist) && fgHist.length) {
    const recent = fgHist.slice(-60);
    for (const p of recent) {
      if (typeof p?.y !== "number" || typeof p?.x !== "number") continue;
      const asOf = cnnTsToIsoDate(p.x);
      if (!asOf) continue;
      fgRows.push({
        indicator_id: "cnn_fear_greed_index",
        as_of: asOf,
        value: p.y,
        unit: "0-100",
        source: "CNN:dataviz",
        meta_json: JSON.stringify({ rating: p.rating ?? null }),
        inserted_at: insertedAt,
      });
    }
  }
  const fg = data?.fear_and_greed;
  if (!fgRows.length && fg && typeof fg.score === "number") {
    const asOf = cnnTsToIsoDate(fg.timestamp) ?? today();
    fgRows.push({
      indicator_id: "cnn_fear_greed_index",
      as_of: asOf,
      value: fg.score,
      unit: "0-100",
      source: "CNN:dataviz",
      meta_json: JSON.stringify({ rating: fg.rating ?? null }),
      inserted_at: insertedAt,
    });
  }
  out.push(...dedupeByDate(fgRows));

  // ── Put/Call Ratio (5-day avg) ────────────────────────────────────────
  // The 0-100 `put_call_options.score` is a normalized sentiment reading —
  // NOT the put/call ratio. The ratio is in `put_call_options.data[].y`
  // (typical range 0.5–1.0), which is what the dashboard thresholds
  // (0.55/0.95) and the existing D1 history expect.
  const pc = data?.put_call_options;
  const pcHist = pc?.data;
  const pcRows: Observation[] = [];
  if (Array.isArray(pcHist) && pcHist.length) {
    const recent = pcHist.slice(-60);
    for (const p of recent) {
      if (typeof p?.y !== "number" || typeof p?.x !== "number") continue;
      const asOf = cnnTsToIsoDate(p.x);
      if (!asOf) continue;
      pcRows.push({
        indicator_id: "cnn_put_call_options",
        as_of: asOf,
        value: p.y,
        unit: "ratio",
        source: "CNN:dataviz",
        meta_json: JSON.stringify({ rating: p.rating ?? null }),
        inserted_at: insertedAt,
      });
    }
  }
  out.push(...dedupeByDate(pcRows));

  return out;
}

// ── S&P 500 P/E Ratio from multpl.com ────────────────────────────────────────
// The page's <meta name="description"> always carries a sentence like
//   "Current S&P 500 PE Ratio is 30.99, a change of +0.31 from previous …"
// which survives their SSR/JS hydration. Simple + reliable.
const SP500_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio";
export async function fetchSp500Pe(): Promise<Observation[]> {
  const html = await fetchHtml(SP500_PE_URL);
  if (!html) return [];
  const m = html.match(
    /content="[^"]*Current\s*S&amp;P\s*500\s*PE\s*Ratio\s*is\s*([0-9]+(?:\.[0-9]+)?)/i,
  ) ?? html.match(
    /content="[^"]*Current\s*S&P\s*500\s*PE\s*Ratio\s*is\s*([0-9]+(?:\.[0-9]+)?)/i,
  );
  if (!m) {
    console.error("fetchSp500Pe: pattern miss on multpl page");
    return [];
  }
  const value = parseFloat(m[1]);
  if (!(value > 0 && value < 500)) return [];

  // multpl's #timestamp block reads e.g.  "4:00 PM EDT, Thu Apr 30"  — no
  // year. Parse the month+day and pin to the most recent past year so
  // we store the actual observation date rather than "today".
  let asOf = today();
  const tsMatch = html.match(
    /\d{1,2}:\d{2}\s*[AP]M\s+[A-Z]{2,4},\s*[A-Za-z]{3,9}\s+([A-Za-z]{3,9})\s+(\d{1,2})/,
  );
  if (tsMatch) {
    const mon = MONTHS[tsMatch[1].toLowerCase()];
    if (mon) asOf = inferYearForMonthDay(mon, tsMatch[2].padStart(2, "0"));
  }

  return [{
    indicator_id: "sp500_pe_ratio",
    as_of: asOf,
    value,
    unit: "x",
    source: "multpl.com",
    meta_json: JSON.stringify({ url: SP500_PE_URL }),
    inserted_at: today(),
  }];
}

// ── Nasdaq 100 % Above 20-Day MA from Barchart ($NDTW) ───────────────────────
// Barchart's page ships the current value in an HTML-entity-escaped JSON
// blob: &quot;dailyLastPrice&quot;:&quot;62.37&quot;
const NDTW_URL = "https://www.barchart.com/stocks/quotes/$NDTW";
export async function fetchNdxAbove20d(): Promise<Observation[]> {
  const html = await fetchHtml(NDTW_URL, "https://www.barchart.com/");
  if (!html) return [];
  // Decode HTML entities for "&quot;" etc. — only for regex purposes.
  const decoded = html.replace(/&quot;/g, '"').replace(/&amp;/g, "&");
  let m = decoded.match(/"dailyLastPrice"\s*:\s*"?([0-9]{1,3}(?:\.[0-9]+)?)"?/);
  if (!m) {
    // Fallback: look for any percentage in range next to "20-Day" text.
    m = decoded.match(
      /(?:20[-\s]?Day|Above[-\s]?20[-\s]?Day|NDTW)[\s\S]{0,400}?([0-9]{1,3}(?:\.[0-9]+)?)\s*%/i,
    );
  }
  if (!m) {
    console.error("fetchNdxAbove20d: pattern miss on Barchart page");
    return [];
  }
  const value = parseFloat(m[1]);
  if (!(value >= 0 && value <= 100)) return [];

  // Barchart embeds the trading day in several JSON fields. The ISO form is
  // the most reliable: "tradeTime":"2026-04-30T21:50:00". Fallback to the
  // US-style "04/30/26" form.
  let asOf = today();
  const isoMatch = decoded.match(/"tradeTime"\s*:\s*"(\d{4}-\d{2}-\d{2})T/);
  if (isoMatch) {
    asOf = isoMatch[1];
  } else {
    const usMatch = decoded.match(/"tradeTime"\s*:\s*"(\d{2})\\?\/(\d{2})\\?\/(\d{2})"/);
    if (usMatch) {
      const mm = usMatch[1];
      const dd = usMatch[2];
      const yy = parseInt(usMatch[3], 10);
      const fullYear = yy < 50 ? 2000 + yy : 1900 + yy;
      asOf = `${fullYear}-${mm}-${dd}`;
    }
  }

  return [{
    indicator_id: "nasdaq100_above_20d_ma",
    as_of: asOf,
    value,
    unit: "percent",
    source: "Barchart.com",
    meta_json: JSON.stringify({ url: NDTW_URL }),
    inserted_at: today(),
  }];
}

// ── Nasdaq 100 P/E from worldperatio.com ─────────────────────────────────────
// Barron's is a Next.js shell (no data in SSR HTML), so use worldperatio,
// whose page embeds:
//   P/E Ratio: <b class="w3-text-black -f14">31.96</b>
//   … font class="...">30 April 2026</font> · P/E Ratio: <b...>31.96</b>
const NDX_PE_URL = "https://worldperatio.com/index/nasdaq-100/";
// Month lookup accepts both 3-letter abbreviations (YCharts, multpl) AND full
// names (worldperatio). "may" appears in both forms so a single entry works.
const MONTHS: Record<string, string> = {
  jan: "01", january: "01",
  feb: "02", february: "02",
  mar: "03", march: "03",
  apr: "04", april: "04",
  may: "05",
  jun: "06", june: "06",
  jul: "07", july: "07",
  aug: "08", august: "08",
  sep: "09", sept: "09", september: "09",
  oct: "10", october: "10",
  nov: "11", november: "11",
  dec: "12", december: "12",
};
/** "30 April 2026" → "2026-04-30". Also accepts "23 Apr 2026". */
function parseEnglishDate(s: string): string | null {
  const m = s.match(/(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{4})/);
  if (!m) return null;
  const day = m[1].padStart(2, "0");
  const mon = MONTHS[m[2].toLowerCase()];
  if (!mon) return null;
  return `${m[3]}-${mon}-${day}`;
}
/** "Apr 23 2026" (month first) → "2026-04-23". */
function parseMonthFirstDate(s: string): string | null {
  const m = s.match(/([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})/);
  if (!m) return null;
  const day = m[2].padStart(2, "0");
  const mon = MONTHS[m[1].toLowerCase()];
  if (!mon) return null;
  return `${m[3]}-${mon}-${day}`;
}
/** Given a (month, day) with no year, pick the most recent past year that
 *  makes the date be ≤ today. Example: on 2026-05-01, "Apr 30" → 2026-04-30;
 *  on 2026-01-02, "Dec 31" → 2025-12-31. */
function inferYearForMonthDay(monIso: string, dayIso: string): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const candidate = new Date(`${y}-${monIso}-${dayIso}T00:00:00Z`);
  if (candidate.getTime() > now.getTime() + 24 * 3600 * 1000) {
    // Future → must be from previous year.
    return `${y - 1}-${monIso}-${dayIso}`;
  }
  return `${y}-${monIso}-${dayIso}`;
}
export async function fetchNasdaq100Pe(): Promise<Observation[]> {
  const html = await fetchHtml(NDX_PE_URL, "https://worldperatio.com/");
  if (!html) return [];
  // Anchor on the labelled P/E Ratio value.
  const valMatch = html.match(
    /P\/E\s*Ratio\s*:\s*<b[^>]*>([0-9]{1,3}(?:\.[0-9]+)?)\s*<\/b>/i,
  ) ?? html.match(
    /Nasdaq\s*100[\s\S]{0,400}?<b[^>]*>([0-9]{1,3}(?:\.[0-9]+)?)\s*<\/b>/i,
  );
  if (!valMatch) {
    console.error("fetchNasdaq100Pe: pattern miss on worldperatio page");
    return [];
  }
  const value = parseFloat(valMatch[1]);
  if (!(value > 5 && value < 200)) return [];

  // Parse a "30 April 2026"-style date near the value if present.
  const dateMatch = html.match(/(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s*<\/font>/i)
    ?? html.match(/(\d{1,2}\s+[A-Za-z]+\s+\d{4})/);
  const asOf = (dateMatch && parseEnglishDate(dateMatch[1])) || today();

  return [{
    indicator_id: "nasdaq100_pe_ratio",
    as_of: asOf,
    value,
    unit: "x",
    source: "WorldPERatio",
    meta_json: JSON.stringify({ url: NDX_PE_URL }),
    inserted_at: today(),
  }];
}

// ── AAII Bull-Bear (via YCharts, stored under bofa_bull_bear slot) ──────────
// Page renders the latest weekly reading inline, e.g.
//   "11.63% for Wk of Apr 23 2026"
const AAII_URL =
  "https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread";
export async function fetchBofaBullBear(): Promise<Observation[]> {
  const html = await fetchHtml(AAII_URL, "https://ycharts.com/");
  if (!html) return [];

  // Primary: "11.63% for Wk of Apr 23 2026" — combined value + date.
  const combined = html.match(
    /([+-]?\d+(?:\.\d+)?)%\s*for\s*Wk\s*of\s*([A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})/i,
  );
  let value: number | null = null;
  let asOf: string | null = null;
  if (combined) {
    value = parseFloat(combined[1]);
    asOf = parseMonthFirstDate(combined[2]);   // "Apr 23 2026" → "2026-04-23"
  }

  // Fallback value: "Last Value ... 11.63%".
  if (value === null) {
    const m2 = html.match(
      /Last Value[\s\S]{0,200}?>\s*([+-]?\d+(?:\.\d+)?)%/i,
    );
    if (m2) value = parseFloat(m2[1]);
  }
  if (value === null || isNaN(value)) {
    console.error("fetchBofaBullBear: pattern miss on ycharts page");
    return [];
  }

  // Fallback date: "Latest Period ... Apr 23 2026".
  if (!asOf) {
    const m3 = html.match(
      /Latest Period[\s\S]{0,150}?>\s*([A-Za-z]{3,9}\s+\d{1,2}\s+\d{4})/i,
    );
    if (m3) asOf = parseMonthFirstDate(m3[1]);
  }

  return [{
    indicator_id: "bofa_bull_bear",
    as_of: asOf ?? today(),
    value,
    unit: "%",
    source: "YCharts:AAII",
    meta_json: JSON.stringify({ url: AAII_URL, definition: "AAII Bull% - Bear%" }),
    inserted_at: today(),
  }];
}

// ── Run all fetchable providers ──────────────────────────────────────────────
export async function fetchAllProviders(env: {
  FRED_API_KEY?: string;
}): Promise<{ ok: string[]; err: string[]; observations: Observation[] }> {
  const ok: string[] = [];
  const err: string[] = [];
  const observations: Observation[] = [];

  const tasks: Array<[string, () => Promise<Observation[]>]> = [
    ["cnn",            fetchCnnFearGreed],
    ["vix",            fetchVix],
    ["sp500_rsi",      fetchSp500Rsi],
    ["cboe_skew",      fetchCboeSkew],
    ["sp500_pe",       fetchSp500Pe],
    ["ndx_above_20d",  fetchNdxAbove20d],
    ["ndx_pe",         fetchNasdaq100Pe],
    ["bofa_bull_bear", fetchBofaBullBear],
    // FRED CSV endpoint requires no key. We pass the key anyway so a
    // future opt-in can switch back to the JSON API via fetchFredJson().
    ["hy_oas",         () => fetchHyOas(env.FRED_API_KEY)],
    ["yc_10y2y",       () => fetchYieldCurve(env.FRED_API_KEY)],
  ];

  // Run in parallel — all tasks are network-bound and totally independent.
  // Previously we did them sequentially which added up to ~60s and
  // occasionally pushed the scheduled run past Workers' budget.
  const results = await Promise.allSettled(
    tasks.map(async ([name, fn]) => ({ name, obs: await fn() })),
  );
  for (const r of results) {
    if (r.status === "fulfilled") {
      observations.push(...r.value.obs);
      ok.push(`${r.value.name}: ${r.value.obs.length} records`);
    } else {
      err.push(`unknown: ${String(r.reason)}`);
    }
  }

  return { ok, err, observations };
}
