/** Raw Finnhub response shape */
interface FinnhubRawArticle {
  headline?: string;
  title?: string;
  summary?: string;
  url?: string;
  datetime?: number;
  date?: number;
  source?: string;
  image?: string;
}

/** Normalised shape expected by the front-end */
export interface NormArticle {
  title: string;
  url: string;
  source: string;
  summary: string;
  datetime: string;
  ts: number;
}

function normalizeArticle(raw: FinnhubRawArticle): NormArticle | null {
  const title = (raw.headline ?? raw.title ?? "").trim();
  if (!title) return null;
  const ts = Number(raw.datetime ?? raw.date ?? 0) || 0;
  let iso = "";
  if (ts > 0) {
    try { iso = new Date(ts * 1000).toISOString(); } catch { /* noop */ }
  }
  return {
    title,
    url: (raw.url ?? "").trim(),
    source: (raw.source ?? "").trim(),
    summary: (raw.summary ?? "").trim().slice(0, 400),
    datetime: iso,
    ts,
  };
}

function normalizeArticles(raw: FinnhubRawArticle[], limit = 8): NormArticle[] {
  const out: NormArticle[] = [];
  for (const r of raw) {
    if (out.length >= limit) break;
    const a = normalizeArticle(r);
    if (a) out.push(a);
  }
  return out;
}

export async function fetchCompanyNews(
  symbol: string,
  from: string,
  to: string,
  finnhubKey: string,
): Promise<NormArticle[]> {
  const url = new URL("https://finnhub.io/api/v1/company-news");
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("from", from);
  url.searchParams.set("to", to);
  url.searchParams.set("token", finnhubKey);

  try {
    const resp = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0" },
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) return [];
    const data = await resp.json() as FinnhubRawArticle[];
    return Array.isArray(data) ? normalizeArticles(data) : [];
  } catch {
    return [];
  }
}

export async function fetchGeneralNews(
  category: string,
  finnhubKey: string,
): Promise<NormArticle[]> {
  const url = new URL("https://finnhub.io/api/v1/news");
  url.searchParams.set("category", category);
  url.searchParams.set("token", finnhubKey);

  try {
    const resp = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0" },
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) return [];
    const data = await resp.json() as FinnhubRawArticle[];
    return Array.isArray(data) ? normalizeArticles(data, 5) : [];
  } catch {
    return [];
  }
}

const INDEX_NEWS_PROXY: Record<string, string> = {
  "^GSPC": "SPY",
  "^DJI":  "DIA",
  "^IXIC": "QQQ",
  "^NDX":  "QQQ",
};

export function newsTickerForYahooSymbol(yahooSymbol: string): string | null {
  const s = yahooSymbol.toUpperCase();
  if (INDEX_NEWS_PROXY[s]) return INDEX_NEWS_PROXY[s];
  if (/[\^=\-]/.test(s) || s.includes("USD")) return null;
  if (/^[A-Z0-9-]+$/.test(s)) return s;
  return null;
}
