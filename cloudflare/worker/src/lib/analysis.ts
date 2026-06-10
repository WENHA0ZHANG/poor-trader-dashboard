import type { YahooBar } from "./yahoo";

// ── Generic indicator helpers ────────────────────────────────────────────────

/** Exponential moving average series (same length as input; leading values
 *  seeded with the first close). */
export function ema(values: number[], period: number): number[] {
  const out: number[] = new Array(values.length).fill(NaN);
  if (values.length === 0 || period <= 1) return values.slice();
  const k = 2 / (period + 1);
  let prev = values[0];
  out[0] = prev;
  for (let i = 1; i < values.length; i++) {
    prev = values[i] * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

/** Wilder's RSI of the closing series. Returns the latest value (or null). */
export function rsi(closes: number[], period = 14): number | null {
  if (closes.length <= period) return null;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) gain += d; else loss -= d;
  }
  let avgGain = gain / period;
  let avgLoss = loss / period;
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    const g = d > 0 ? d : 0;
    const l = d < 0 ? -d : 0;
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
  }
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

/** Average True Range over the last `period` bars (simple mean of TR). */
export function atr(bars: YahooBar[], period = 14): number | null {
  if (bars.length < period + 1) return null;
  const trs: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const h = bars[i].high;
    const l = bars[i].low;
    const pc = bars[i - 1].close;
    trs.push(Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc)));
  }
  const slice = trs.slice(-period);
  return slice.reduce((s, v) => s + v, 0) / slice.length;
}

/** Average Daily Range as a percentage: mean of (high/low - 1) over `period`. */
export function adrPct(bars: YahooBar[], period = 20): number | null {
  if (bars.length < 2) return null;
  const slice = bars.slice(-period).filter((b) => b.low > 0);
  if (!slice.length) return null;
  const sum = slice.reduce((s, b) => s + (b.high / b.low - 1), 0);
  return (sum / slice.length) * 100;
}

function pctChange(cur: number, prev: number | null | undefined): number | null {
  if (prev == null || prev === 0) return null;
  return Math.round((cur / prev - 1) * 10000) / 100;
}

function r2(n: number): number {
  return Math.round(n * 100) / 100;
}

// ── Pattern detection (heuristic) ────────────────────────────────────────────
// Generic momentum-continuation heuristics. Flags a recent run-up ("pole")
// followed by a tight, shallow consolidation ("flag"). No proprietary
// methodology is reproduced.

export interface PatternResult {
  high_tight_flag: boolean;
  bull_flag: boolean;
  flag_start: string | null;
  flag_end: string | null;
  pole_start: string | null;
  pivot: number | null;
}

export function detectPatterns(bars: YahooBar[]): PatternResult {
  const empty: PatternResult = {
    high_tight_flag: false, bull_flag: false,
    flag_start: null, flag_end: null, pole_start: null, pivot: null,
  };
  const n = bars.length;
  if (n < 30) return empty;

  const closes = bars.map((b) => b.close);
  const last = bars[n - 1];

  let best: PatternResult | null = null;
  for (let flagLen = 3; flagLen <= 20 && flagLen < n - 10; flagLen++) {
    const flag = bars.slice(n - flagLen);
    const flagHigh = Math.max(...flag.map((b) => b.high));
    const flagLow = Math.min(...flag.map((b) => b.low));
    const flagDepth = (flagHigh - flagLow) / flagHigh;

    const poleLookback = Math.min(40, n - flagLen);
    const poleStartIdx = n - flagLen - poleLookback;
    const poleBase = Math.min(...closes.slice(Math.max(0, poleStartIdx), n - flagLen));
    const poleTop = flagHigh;
    const poleGain = poleBase > 0 ? poleTop / poleBase - 1 : 0;
    const pullback = (poleTop - flagLow) / poleTop;
    const nearHighs = last.close >= flagHigh * 0.78;

    if (!nearHighs) continue;

    const isHTF =
      poleGain >= 0.8 &&
      flagLen <= 12 &&
      flagDepth <= 0.25 &&
      pullback <= 0.30;

    const isBull =
      poleGain >= 0.2 &&
      flagLen <= 15 &&
      flagDepth <= 0.18 &&
      pullback <= 0.25;

    if (isHTF || isBull) {
      const candidate: PatternResult = {
        high_tight_flag: isHTF,
        bull_flag: isBull && !isHTF,
        flag_start: bars[n - flagLen].date,
        flag_end: last.date,
        pole_start: bars[Math.max(0, poleStartIdx)].date,
        pivot: r2(flagHigh),
      };
      if (!best || (isHTF && !best.high_tight_flag) || flagDepth < 0.1) {
        best = candidate;
        if (isHTF) break;
      }
    }
  }
  return best ?? empty;
}

// ── Full metric bundle for one symbol ────────────────────────────────────────

export interface WatchMetrics {
  symbol: string;
  price: number | null;
  as_of: string | null;
  chg_1d_pct: number | null;
  chg_1w_pct: number | null;
  chg_1m_pct: number | null;
  chg_3m_pct: number | null;
  chg_6m_pct: number | null;
  lod: number | null;
  hod: number | null;
  adr_pct: number | null;
  atr: number | null;
  atr_pct: number | null;
  rsi: number | null;
  ema8: number | null;
  ema21: number | null;
  ema50: number | null;
  vol_today: number | null;
  vol_avg_1m: number | null;
  vol_ratio: number | null;
  vol_doubled: boolean;
  hve: boolean;
  extended: boolean;
  dollar_vol: number | null;
  high_tight_flag: boolean;
  bull_flag: boolean;
  pivot: number | null;
  stop: number | null;
  stop_pct: number | null;
  risk: number | null;
  tp1: number | null;
  tp2: number | null;
  focus_score: number;
  focus_reasons: string[];
  pattern: PatternResult;
  ok: boolean;
}

export function computeMetrics(symbol: string, bars: YahooBar[]): WatchMetrics {
  const base: WatchMetrics = {
    symbol,
    price: null, as_of: null,
    chg_1d_pct: null, chg_1w_pct: null, chg_1m_pct: null, chg_3m_pct: null, chg_6m_pct: null,
    lod: null, hod: null, adr_pct: null, atr: null, atr_pct: null, rsi: null,
    ema8: null, ema21: null, ema50: null,
    vol_today: null, vol_avg_1m: null, vol_ratio: null, vol_doubled: false,
    hve: false, extended: false, dollar_vol: null,
    high_tight_flag: false, bull_flag: false, pivot: null,
    stop: null, stop_pct: null, risk: null, tp1: null, tp2: null,
    focus_score: 0, focus_reasons: [],
    pattern: { high_tight_flag: false, bull_flag: false, flag_start: null, flag_end: null, pole_start: null, pivot: null },
    ok: false,
  };
  const n = bars.length;
  if (n < 2) return base;

  const last = bars[n - 1];
  const closes = bars.map((b) => b.close);
  const price = last.close;

  base.ok = true;
  base.price = r2(price);
  base.as_of = last.date;
  base.lod = r2(last.low);
  base.hod = r2(last.high);

  base.chg_1d_pct = pctChange(price, closes[n - 2]);
  base.chg_1w_pct = pctChange(price, closes[n - 6]);
  base.chg_1m_pct = pctChange(price, closes[n - 22]);
  base.chg_3m_pct = pctChange(price, closes[n - 64]);
  base.chg_6m_pct = pctChange(price, closes[n - 127]);

  base.adr_pct = round2OrNull(adrPct(bars, 20));
  const a = atr(bars, 14);
  base.atr = round2OrNull(a);
  base.atr_pct = a != null && price ? r2((a / price) * 100) : null;
  base.rsi = round2OrNull(rsi(closes, 14));

  const e8 = ema(closes, 8);
  const e21 = ema(closes, 21);
  const e50 = ema(closes, 50);
  base.ema8 = r2(e8[n - 1]);
  base.ema21 = r2(e21[n - 1]);
  base.ema50 = r2(e50[n - 1]);

  const volToday = last.volume || 0;
  const priorVols = bars.slice(Math.max(0, n - 22), n - 1).map((b) => b.volume || 0).filter((v) => v > 0);
  const volAvg = priorVols.length ? priorVols.reduce((s, v) => s + v, 0) / priorVols.length : null;
  base.vol_today = volToday || null;
  base.vol_avg_1m = volAvg != null ? Math.round(volAvg) : null;
  base.vol_ratio = volAvg && volAvg > 0 ? r2(volToday / volAvg) : null;
  base.vol_doubled = (base.vol_ratio ?? 0) >= 2;
  base.dollar_vol = volAvg != null ? Math.round(volAvg * price) : null;

  const maxVol = Math.max(...bars.map((b) => b.volume || 0));
  base.hve = volToday > 0 && volToday >= maxVol;

  if (a != null && base.ema50 != null) {
    base.extended = price >= base.ema50 + 7 * a;
  }

  const pat = detectPatterns(bars);
  base.pattern = pat;
  base.high_tight_flag = pat.high_tight_flag;
  base.bull_flag = pat.bull_flag;
  base.pivot = pat.pivot;

  // Suggested swing levels — stop distance is the smaller of ADR%, ATR%
  // and 7% (generic risk sizing); targets are simple R-multiples.
  const candidates = [7];
  if (base.adr_pct != null && base.adr_pct > 0) candidates.push(base.adr_pct);
  if (base.atr_pct != null && base.atr_pct > 0) candidates.push(base.atr_pct);
  const stopPct = Math.min(...candidates);
  if (price > 0 && stopPct > 0) {
    const stop = price * (1 - stopPct / 100);
    const riskAmt = price - stop;
    base.stop = r2(stop);
    base.stop_pct = r2(stopPct);
    base.risk = r2(riskAmt);
    base.tp1 = r2(price + 3 * riskAmt);
    base.tp2 = r2(price + 5 * riskAmt);
  }

  let score = 0;
  const reasons: string[] = [];
  if (base.vol_doubled) { score += 4; reasons.push("VOL_DOUBLED"); }
  else if ((base.vol_ratio ?? 0) >= 1.5) { score += 2; reasons.push("VOL_SURGE"); }
  if (base.hve) { score += 3; reasons.push("HVE"); }
  if (base.high_tight_flag) { score += 4; reasons.push("HTF"); }
  if (base.bull_flag) { score += 3; reasons.push("BULL_FLAG"); }
  if ((base.chg_1m_pct ?? 0) >= 30) { score += 1; reasons.push("STRONG_1M"); }
  if (base.ema8 != null && base.ema21 != null && base.ema50 != null &&
      base.ema8 > base.ema21 && base.ema21 > base.ema50) { score += 1; reasons.push("TREND_UP"); }
  if (base.extended) { reasons.push("EXTENDED"); }
  base.focus_score = score;
  base.focus_reasons = reasons;

  return base;
}

function round2OrNull(v: number | null): number | null {
  return v == null || Number.isNaN(v) ? null : r2(v);
}
