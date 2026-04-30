import type { Observation, Signal } from "./types";

/**
 * Port of Python signals.py — computes bull/bear alert signals from the
 * latest indicator readings.
 */
export function computeSignals(
  latest: Record<string, Observation>,
): Signal[] {
  const out: Signal[] = [];

  // 1) AAII Bull-Bear Spread
  const bb = latest["bofa_bull_bear"];
  if (bb) {
    const v = bb.value;
    out.push({
      indicator_id: "bofa_bull_bear",
      top: v >= 20,
      bottom: v <= -20,
      title: "Investor Sentiment Bull-Bear Spread",
      detail: `${v.toFixed(2)}% (≥ +20 top sentiment; ≤ −20 bottom sentiment)`,
    });
  }

  // 2) CNN Fear & Greed
  const fg = latest["cnn_fear_greed_index"];
  if (fg) {
    const v = fg.value;
    let meta: Record<string, unknown> | undefined;
    try { meta = fg.meta_json ? JSON.parse(fg.meta_json) : undefined; } catch { /* noop */ }
    out.push({
      indicator_id: "cnn_fear_greed_index",
      top: v >= 75,
      bottom: v <= 25,
      title: "Fear & Greed Index",
      detail: `${v.toFixed(1)} (≥ 75 extreme greed; ≤ 25 extreme fear)`,
      meta: meta ?? null,
    });
  }

  // 3) CNN Put/Call
  const pc = latest["cnn_put_call_options"];
  if (pc) {
    const v = pc.value;
    out.push({
      indicator_id: "cnn_put_call_options",
      top: v < 0.55,
      bottom: v >= 0.95,
      title: "Put/Call Ratio (5-Day Average)",
      detail: `${v.toFixed(2)} (< 0.55 extreme greed; ≥ 0.95 panic put-buying)`,
    });
  }

  // 4) VIX
  const vix = latest["vix"];
  if (vix) {
    const v = vix.value;
    out.push({
      indicator_id: "vix",
      top: v < 14,
      bottom: v > 25,
      title: "S&P 500 Volatility Index",
      detail: `${v.toFixed(2)} (< 14 complacency; > 25 fear / > 30 panic)`,
    });
  }

  // 5) S&P 500 RSI
  const rsi = latest["sp500_rsi"];
  if (rsi) {
    const v = rsi.value;
    out.push({
      indicator_id: "sp500_rsi",
      top: v >= 70,
      bottom: v <= 30,
      title: "S&P 500 Relative Strength Index",
      detail: `${v.toFixed(2)} (> 70 overbought; < 30 oversold)`,
    });
  }

  // 6) S&P 500 PE
  const sppe = latest["sp500_pe_ratio"];
  if (sppe) {
    const v = sppe.value;
    out.push({
      indicator_id: "sp500_pe_ratio",
      top: v >= 30,
      bottom: v <= 20,
      title: "S&P 500 Price-to-Earnings Ratio",
      detail: `${v.toFixed(2)}x (≥ 30 top valuation; ≤ 20 bottom valuation)`,
    });
  }

  // 7) Nasdaq 100 PE
  const ndxpe = latest["nasdaq100_pe_ratio"];
  if (ndxpe) {
    const v = ndxpe.value;
    out.push({
      indicator_id: "nasdaq100_pe_ratio",
      top: v > 35,
      bottom: v < 22,
      title: "Nasdaq 100 Price-to-Earnings Ratio",
      detail: `${v.toFixed(2)}x (> 35 top valuation; < 22 bottom valuation)`,
    });
  }

  // 8) Nasdaq 100 > 20d MA
  const ndtw = latest["nasdaq100_above_20d_ma"];
  if (ndtw) {
    const v = ndtw.value;
    out.push({
      indicator_id: "nasdaq100_above_20d_ma",
      top: v > 80,
      bottom: v < 20,
      title: "Nasdaq 100 Above 20-Day Moving Average (%)",
      detail: `${v.toFixed(2)}% (> 80 top; < 20 bottom)`,
    });
  }

  // 9) HY OAS
  const hy = latest["us_high_yield_spread"];
  if (hy) {
    const raw = hy.value;
    const bp = (hy.unit === "percent" || raw < 30) ? raw * 100 : raw;
    const pct = bp / 100;
    out.push({
      indicator_id: "us_high_yield_spread",
      top: bp < 280,
      bottom: bp > 450,
      title: "US High Yield Option-Adjusted Spread",
      detail: `Current ${pct.toFixed(2)}% (< 2.8% credit-greed top; > 4.5% credit-stress bottom)`,
    });
  }

  // 10) CBOE SKEW
  const skew = latest["cboe_skew"];
  if (skew) {
    const v = skew.value;
    out.push({
      indicator_id: "cboe_skew",
      top: v >= 155,
      bottom: false,
      title: "CBOE SKEW (Tail-Risk Hedging)",
      detail: `${v.toFixed(1)} (≥ 155 institutional tail-hedging spike — top warning)`,
    });
  }

  // 11) 10Y-2Y Yield Curve
  const yc = latest["yc_10y_2y"];
  if (yc) {
    const v = yc.value;
    out.push({
      indicator_id: "yc_10y_2y",
      top: v >= -0.05 && v <= 0.6,
      bottom: v >= 1.5,
      title: "10Y-2Y Treasury Yield Curve",
      detail: `${v >= 0 ? "+" : ""}${v.toFixed(2)}% (re-steepening from inversion: late-cycle top window; ≥ 1.5% Fed-easing-driven bottom window)`,
    });
  }

  return out;
}
