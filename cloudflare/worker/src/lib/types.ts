export interface Env {
  DB: D1Database;
  FINNHUB_KEY?: string;
  FRED_API_KEY?: string;
  ENVIRONMENT?: string;
}

export interface Observation {
  indicator_id: string;
  as_of: string;
  value: number;
  unit: string;
  source: string;
  meta_json?: string | null;
  inserted_at: string;
}

export interface Signal {
  indicator_id: string;
  top: boolean;
  bottom: boolean;
  title: string;
  detail: string;
  meta?: Record<string, unknown> | null;
}

export interface RegimeContribution {
  indicator_id: string;
  title: string;
  value: number;
  unit: string;
  tier: number;
  weight: number;
  points: number;
  reason: string;
}

export interface MarketRegime {
  score: number;
  buy_points: number;
  risk_points: number;
  label: string;
  css_class: string;
  summary: string;
  contributions: RegimeContribution[];
  coverage: number;
  total: number;
  yc_recently_inverted: boolean;
}

export const ALL_INDICATOR_IDS = [
  "cnn_fear_greed_index",
  "cnn_put_call_options",
  "vix",
  "bofa_bull_bear",
  "sp500_rsi",
  "sp500_pe_ratio",
  "nasdaq100_pe_ratio",
  "nasdaq100_above_20d_ma",
  "us_high_yield_spread",
  "cboe_skew",
  "yc_10y_2y",
] as const;

export type IndicatorId = (typeof ALL_INDICATOR_IDS)[number];
