interface YahooChartPoint {
  date: string;
  close: number;
}

export async function fetchYahooChart(
  symbol: string,
  range = "1y",
  interval = "1d",
): Promise<YahooChartPoint[]> {
  const url = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  url.searchParams.set("range", range);
  url.searchParams.set("interval", interval);
  url.searchParams.set("includePrePost", "false");

  const resp = await fetch(url.toString(), {
    headers: {
      "User-Agent": "Mozilla/5.0",
      Accept: "application/json",
    },
    cf: { cacheTtl: 300, cacheEverything: false },
  });

  if (!resp.ok) return [];

  try {
    const data = await resp.json() as {
      chart?: { result?: Array<{
        timestamp?: number[];
        indicators?: { quote?: Array<{ close?: (number | null)[] }> };
      }> };
    };
    const result = data?.chart?.result?.[0];
    if (!result) return [];
    const timestamps = result.timestamp ?? [];
    const closes = result.indicators?.quote?.[0]?.close ?? [];

    const out: YahooChartPoint[] = [];
    for (let i = 0; i < timestamps.length; i++) {
      const c = closes[i];
      if (c == null) continue;
      const d = new Date(timestamps[i] * 1000).toISOString().slice(0, 10);
      out.push({ date: d, close: c });
    }
    return out;
  } catch {
    return [];
  }
}

export interface YahooQuote {
  date: string;
  close: number;
  open?: number;
  high?: number;
  low?: number;
}

/** Fetch a single current quote (latest close, 1d change) from Yahoo Finance. */
export async function fetchYahooQuote(symbol: string): Promise<YahooQuote | null> {
  const points = await fetchYahooChart(symbol, "5d", "1d");
  if (!points.length) return null;
  return points[points.length - 1];
}

export interface YahooBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Fetch full OHLCV daily bars from Yahoo Finance. Unlike fetchYahooChart
 * (which only keeps `close`), this preserves open/high/low/volume so the
 * Watchlist page can compute range/volatility/volume metrics and draw
 * candlesticks.
 */
export async function fetchYahooOHLCV(
  symbol: string,
  range = "1y",
  interval = "1d",
): Promise<YahooBar[]> {
  const url = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  url.searchParams.set("range", range);
  url.searchParams.set("interval", interval);
  url.searchParams.set("includePrePost", "false");

  const resp = await fetch(url.toString(), {
    headers: { "User-Agent": "Mozilla/5.0", Accept: "application/json" },
    cf: { cacheTtl: 300, cacheEverything: false },
  });
  if (!resp.ok) return [];

  try {
    const data = await resp.json() as {
      chart?: { result?: Array<{
        timestamp?: number[];
        indicators?: { quote?: Array<{
          open?: (number | null)[];
          high?: (number | null)[];
          low?: (number | null)[];
          close?: (number | null)[];
          volume?: (number | null)[];
        }> };
      }> };
    };
    const result = data?.chart?.result?.[0];
    if (!result) return [];
    const ts = result.timestamp ?? [];
    const q = result.indicators?.quote?.[0] ?? {};
    const opens = q.open ?? [];
    const highs = q.high ?? [];
    const lows = q.low ?? [];
    const closes = q.close ?? [];
    const vols = q.volume ?? [];

    const out: YahooBar[] = [];
    for (let i = 0; i < ts.length; i++) {
      const c = closes[i];
      const h = highs[i];
      const l = lows[i];
      const o = opens[i];
      if (c == null || h == null || l == null || o == null) continue;
      out.push({
        date: new Date(ts[i] * 1000).toISOString().slice(0, 10),
        open: o, high: h, low: l, close: c,
        volume: vols[i] ?? 0,
      });
    }
    return out;
  } catch {
    return [];
  }
}
