import type { Observation, MarketRegime, RegimeContribution } from "./types";
import { ALL_INDICATOR_IDS } from "./types";

const WEIGHTS: Record<string, number> = {
  vix: 1.5,
  us_high_yield_spread: 1.5,
  sp500_pe_ratio: 1.2,
  cnn_fear_greed_index: 1.0,
  cnn_put_call_options: 1.0,
  nasdaq100_above_20d_ma: 1.0,
  yc_10y_2y: 1.0,
  bofa_bull_bear: 0.7,
  sp500_rsi: 0.7,
  nasdaq100_pe_ratio: 0.7,
  cboe_skew: 0.6,
};

const BANDS: [number, string, string][] = [
  [9.0,  "Strong Buy",   "regime-strong-buy"],
  [4.5,  "Buy",          "regime-buy"],
  [1.5,  "Cautious Buy", "regime-cautious-buy"],
  [-1.5, "Neutral",      "regime-neutral"],
  [-4.5, "Caution",      "regime-caution"],
  [-9.0, "Risk",         "regime-risk"],
  [-Infinity, "Strong Risk", "regime-strong-risk"],
];

function scoreOne(
  o: Observation,
  recentlyInverted: boolean,
): RegimeContribution | null {
  const id = o.indicator_id;
  const v = o.value;
  const w = WEIGHTS[id] ?? 1.0;

  function c(title: string, value: number, unit: string, tier: number, reason: string): RegimeContribution {
    return { indicator_id: id, title, value, unit, tier, weight: w, points: Math.round(tier * w * 100) / 100, reason };
  }

  if (id === "vix") {
    if (v >= 40) return c("VIX", v, "", +3, `VIX ${v.toFixed(1)} ≥ 40 panic capitulation`);
    if (v >= 30) return c("VIX", v, "", +2, `VIX ${v.toFixed(1)} > 30 fear`);
    if (v > 25)  return c("VIX", v, "", +1, `VIX ${v.toFixed(1)} > 25 elevated fear`);
    if (v < 12)  return c("VIX", v, "", -2, `VIX ${v.toFixed(1)} < 12 extreme complacency`);
    if (v < 14)  return c("VIX", v, "", -1, `VIX ${v.toFixed(1)} < 14 complacency`);
    return c("VIX", v, "", 0, "VIX in normal range");
  }

  if (id === "cnn_fear_greed_index") {
    if (v <= 10) return c("Fear & Greed", v, "", +3, `F&G ${v.toFixed(0)} ≤ 10 capitulation`);
    if (v <= 20) return c("Fear & Greed", v, "", +2, `F&G ${v.toFixed(0)} ≤ 20 extreme fear`);
    if (v <= 25) return c("Fear & Greed", v, "", +1, `F&G ${v.toFixed(0)} ≤ 25 fear`);
    if (v >= 85) return c("Fear & Greed", v, "", -2, `F&G ${v.toFixed(0)} ≥ 85 extreme greed`);
    if (v >= 75) return c("Fear & Greed", v, "", -1, `F&G ${v.toFixed(0)} ≥ 75 greed`);
    return c("Fear & Greed", v, "", 0, "F&G in normal range");
  }

  if (id === "cnn_put_call_options") {
    if (v >= 1.20) return c("Put/Call (5d)", v, "", +3, `P/C ${v.toFixed(2)} ≥ 1.20 panic put-buying`);
    if (v >= 1.05) return c("Put/Call (5d)", v, "", +2, `P/C ${v.toFixed(2)} ≥ 1.05 heavy put-buying`);
    if (v >= 0.95) return c("Put/Call (5d)", v, "", +1, `P/C ${v.toFixed(2)} ≥ 0.95 elevated fear`);
    if (v < 0.50)  return c("Put/Call (5d)", v, "", -2, `P/C ${v.toFixed(2)} < 0.50 extreme call greed`);
    if (v < 0.55)  return c("Put/Call (5d)", v, "", -1, `P/C ${v.toFixed(2)} < 0.55 call greed`);
    return c("Put/Call (5d)", v, "", 0, "P/C in normal range");
  }

  if (id === "bofa_bull_bear") {
    if (v <= -30) return c("AAII Bull-Bear", v, "%", +2, `${v.toFixed(1)}% ≤ −30 deep bearish sentiment`);
    if (v <= -20) return c("AAII Bull-Bear", v, "%", +1, `${v.toFixed(1)}% ≤ −20 bearish sentiment`);
    if (v >= 30)  return c("AAII Bull-Bear", v, "%", -2, `${v.toFixed(1)}% ≥ +30 deep bullish sentiment`);
    if (v >= 20)  return c("AAII Bull-Bear", v, "%", -1, `${v.toFixed(1)}% ≥ +20 bullish sentiment`);
    return c("AAII Bull-Bear", v, "%", 0, "Sentiment in normal range");
  }

  if (id === "sp500_rsi") {
    if (v < 25)  return c("S&P 500 RSI", v, "", +2, `RSI ${v.toFixed(1)} < 25 deeply oversold`);
    if (v < 30)  return c("S&P 500 RSI", v, "", +1, `RSI ${v.toFixed(1)} < 30 oversold`);
    if (v > 80)  return c("S&P 500 RSI", v, "", -2, `RSI ${v.toFixed(1)} > 80 deeply overbought`);
    if (v > 70)  return c("S&P 500 RSI", v, "", -1, `RSI ${v.toFixed(1)} > 70 overbought`);
    return c("S&P 500 RSI", v, "", 0, "RSI in normal range");
  }

  if (id === "us_high_yield_spread") {
    const bp = (o.unit === "bp" || v > 30) ? v : v * 100;
    const pct = bp / 100;
    if (bp >= 700) return c("HY OAS", pct, "%", +3, `HY ${pct.toFixed(2)}% ≥ 7% credit panic`);
    if (bp >= 550) return c("HY OAS", pct, "%", +2, `HY ${pct.toFixed(2)}% ≥ 5.5% credit stress`);
    if (bp >= 450) return c("HY OAS", pct, "%", +1, `HY ${pct.toFixed(2)}% ≥ 4.5% credit stress`);
    if (bp <= 250) return c("HY OAS", pct, "%", -2, `HY ${pct.toFixed(2)}% ≤ 2.5% credit complacency`);
    if (bp <= 280) return c("HY OAS", pct, "%", -1, `HY ${pct.toFixed(2)}% ≤ 2.8% credit-greed`);
    return c("HY OAS", pct, "%", 0, "HY OAS in normal range");
  }

  if (id === "nasdaq100_above_20d_ma") {
    if (v < 10)  return c("NDX > 20d MA", v, "%", +2, `${v.toFixed(0)}% < 10 broad capitulation`);
    if (v < 20)  return c("NDX > 20d MA", v, "%", +1, `${v.toFixed(0)}% < 20 broad selloff`);
    if (v > 90)  return c("NDX > 20d MA", v, "%", -2, `${v.toFixed(0)}% > 90 extreme breadth thrust`);
    if (v > 80)  return c("NDX > 20d MA", v, "%", -1, `${v.toFixed(0)}% > 80 stretched breadth`);
    return c("NDX > 20d MA", v, "%", 0, "Breadth in normal range");
  }

  if (id === "sp500_pe_ratio") {
    if (v <= 18) return c("S&P 500 PE", v, "x", +2, `PE ${v.toFixed(1)}x ≤ 18 deep value`);
    if (v <= 20) return c("S&P 500 PE", v, "x", +1, `PE ${v.toFixed(1)}x ≤ 20 cheap valuation`);
    if (v >= 33) return c("S&P 500 PE", v, "x", -2, `PE ${v.toFixed(1)}x ≥ 33 extreme valuation`);
    if (v >= 30) return c("S&P 500 PE", v, "x", -1, `PE ${v.toFixed(1)}x ≥ 30 expensive`);
    return c("S&P 500 PE", v, "x", 0, "PE in normal range");
  }

  if (id === "nasdaq100_pe_ratio") {
    if (v < 22) return c("NDX 100 PE", v, "x", +1, `NDX PE ${v.toFixed(1)}x < 22 cheap`);
    if (v > 35) return c("NDX 100 PE", v, "x", -1, `NDX PE ${v.toFixed(1)}x > 35 expensive`);
    return c("NDX 100 PE", v, "x", 0, "NDX PE in normal range");
  }

  if (id === "cboe_skew") {
    if (v >= 160) return c("CBOE SKEW", v, "", -2, `SKEW ${v.toFixed(1)} ≥ 160 extreme tail-hedging`);
    if (v >= 155) return c("CBOE SKEW", v, "", -1, `SKEW ${v.toFixed(1)} ≥ 155 tail-hedging spike`);
    return c("CBOE SKEW", v, "", 0, "SKEW in normal range");
  }

  if (id === "yc_10y_2y") {
    if (recentlyInverted && v >= -0.05 && v <= 0.6) {
      return c("10Y-2Y Curve", v, "%", -1, `${v >= 0 ? "+" : ""}${v.toFixed(2)}% in re-steepening top window after recent inversion`);
    }
    return c("10Y-2Y Curve", v, "%", 0, "Curve in normal range");
  }

  return null;
}

function classify(score: number): [string, string] {
  for (const [threshold, label, css] of BANDS) {
    if (score >= threshold) return [label, css];
  }
  return ["Strong Risk", "regime-strong-risk"];
}

export function computeMarketRegime(
  latest: Record<string, Observation>,
  ycRecentlyInverted = true,
): MarketRegime {
  const contributions: RegimeContribution[] = [];
  let considered = 0;

  for (const id of Object.keys(latest)) {
    considered++;
    const c = scoreOne(latest[id], ycRecentlyInverted);
    if (c) contributions.push(c);
  }

  const buy = Math.round(contributions.filter((c) => c.points > 0).reduce((s, c) => s + c.points, 0) * 100) / 100;
  const risk = Math.round(contributions.filter((c) => c.points < 0).reduce((s, c) => s - c.points, 0) * 100) / 100;
  const score = Math.round((buy - risk) * 100) / 100;
  const [label, css_class] = classify(score);

  const fired = contributions.filter((c) => c.tier !== 0).sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
  let summary = "All indicators in normal ranges.";
  if (fired.length) {
    const pos = fired.filter((c) => c.points > 0);
    const neg = fired.filter((c) => c.points < 0);
    const parts: string[] = [];
    if (pos.length) parts.push("Bottom signals: " + pos.map((c) => `${c.title} (${c.points >= 0 ? "+" : ""}${c.points.toFixed(1)})`).join(", "));
    if (neg.length) parts.push("Top signals: " + neg.map((c) => `${c.title} (${c.points >= 0 ? "+" : ""}${c.points.toFixed(1)})`).join(", "));
    summary = parts.join(" · ");
  }

  const order = Object.fromEntries(ALL_INDICATOR_IDS.map((id, i) => [id, i]));
  const sorted = [...contributions].sort((a, b) => (order[a.indicator_id] ?? 999) - (order[b.indicator_id] ?? 999));

  return {
    score,
    buy_points: buy,
    risk_points: risk,
    label,
    css_class,
    summary,
    contributions: sorted,
    coverage: contributions.filter((c) => c.tier !== 0).length,
    total: considered,
    yc_recently_inverted: ycRecentlyInverted,
  };
}
