interface StooqRow {
  date: string;
  close: number;
}

function parseStooqCsv(text: string): StooqRow[] {
  const lines = text.trim().split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  const rows: StooqRow[] = [];
  for (const line of lines.slice(1)) {
    const parts = line.split(",");
    // Stooq daily: Date,Open,High,Low,Close,Volume
    if (parts.length < 5) continue;
    const date = parts[0].trim();
    const close = parseFloat(parts[4]);
    if (isNaN(close)) continue;
    rows.push({ date, close });
  }
  return rows;
}

export async function fetchStooqDailyCloses(
  symbol: string,
  start: string,
  end: string,
): Promise<StooqRow[]> {
  const url = new URL("https://stooq.com/q/d/l/");
  url.searchParams.set("s", symbol);
  url.searchParams.set("i", "d");
  url.searchParams.set("d1", start.replace(/-/g, ""));
  url.searchParams.set("d2", end.replace(/-/g, ""));

  try {
    const resp = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity" },
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) return [];
    const text = await resp.text();
    if (!text || text.toLowerCase().startsWith("no data")) return [];
    return parseStooqCsv(text);
  } catch {
    return [];
  }
}

export async function fetchStooqQuote(symbol: string): Promise<StooqRow | null> {
  const url = new URL("https://stooq.com/q/l/");
  url.searchParams.set("s", symbol);
  url.searchParams.set("f", "sd2t2ohlcv");
  url.searchParams.set("h", "");
  url.searchParams.set("e", "csv");

  try {
    const resp = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity" },
      signal: AbortSignal.timeout(6000),
    });
    if (!resp.ok) return null;
    const text = await resp.text();
    const lines = text.trim().split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length < 2) return null;
    // Symbol,Date,Time,Open,High,Low,Close,Volume
    const parts = lines[1].split(",");
    if (parts.length < 7) return null;
    return { date: parts[1].trim(), close: parseFloat(parts[6]) };
  } catch {
    return null;
  }
}

export type { StooqRow };
