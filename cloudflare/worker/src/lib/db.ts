import type { D1Database } from "@cloudflare/workers-types";
import type { Observation } from "./types";

export async function getLatestObservations(
  db: D1Database,
): Promise<Record<string, Observation>> {
  const rows = await db
    .prepare(
      `SELECT o.*
       FROM observations o
       JOIN (
         SELECT indicator_id, MAX(as_of) AS max_as_of
         FROM observations
         GROUP BY indicator_id
       ) latest
       ON o.indicator_id = latest.indicator_id
       AND o.as_of = latest.max_as_of`,
    )
    .all<Observation>();

  const out: Record<string, Observation> = {};
  for (const r of rows.results) {
    out[r.indicator_id] = r;
  }
  return out;
}

export async function getRecentObservations(
  db: D1Database,
  indicatorId: string,
  days: number,
): Promise<Observation[]> {
  const cutoff = new Date(Date.now() - days * 86400 * 1000)
    .toISOString()
    .slice(0, 10);
  const rows = await db
    .prepare(
      `SELECT * FROM observations
       WHERE indicator_id = ? AND as_of >= ?
       ORDER BY as_of ASC`,
    )
    .bind(indicatorId, cutoff)
    .all<Observation>();
  return rows.results;
}

export async function upsertObservations(
  db: D1Database,
  observations: Observation[],
): Promise<void> {
  if (!observations.length) return;
  const now = new Date().toISOString().replace("T", " ").slice(0, 19) + "Z";
  const stmts = observations.map((o) =>
    db
      .prepare(
        `INSERT INTO observations (indicator_id, as_of, value, unit, source, meta_json, inserted_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(indicator_id, as_of)
         DO UPDATE SET
           value=excluded.value,
           unit=excluded.unit,
           source=excluded.source,
           meta_json=excluded.meta_json,
           inserted_at=excluded.inserted_at`,
      )
      .bind(
        o.indicator_id,
        o.as_of,
        o.value,
        o.unit,
        o.source,
        o.meta_json ?? null,
        now,
      ),
  );
  await db.batch(stmts);
}

/**
 * Normalize a SQLite-style timestamp string into a strict UTC ISO 8601
 * string (e.g. `"2026-04-30T06:00:00Z"`). SQLite's `datetime('now')`
 * returns `"YYYY-MM-DD HH:MM:SS"` without a `Z`, which several browser
 * `Date()` parsers interpret as *local* time — that's the root cause of
 * the dashboard's "Last Updated" timestamp appearing to jump by the
 * client's TZ offset (e.g. 8h in SGT).
 */
function _normalizeUtcTs(s: string | null | undefined): string | null {
  if (!s) return null;
  let t = String(s).trim();
  if (!t) return null;
  if (t.endsWith("Z") || t.endsWith("z")) t = t.slice(0, -1);
  t = t.replace(" ", "T");
  // Must look like YYYY-MM-DDTHH:MM:SS at minimum.
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t)) return null;
  return t + "Z";
}

export async function getLastUpdateTime(db: D1Database): Promise<string | null> {
  // The "last update" surfaced to the UI is the most recent of:
  //   • any indicator observation insert, or
  //   • the cron heartbeat (see setLastCronRun below — written on every
  //     scheduled run so the timestamp keeps moving even when no source
  //     produced new data on that run).
  const obs = await db
    .prepare(`SELECT MAX(inserted_at) AS t FROM observations`)
    .first<{ t: string | null }>();
  const heartbeat = await db
    .prepare(`SELECT value AS t FROM kv_store WHERE key = 'last_cron_run'`)
    .first<{ t: string | null }>();
  const candidates = [
    _normalizeUtcTs(obs?.t),
    _normalizeUtcTs(heartbeat?.t),
  ].filter((s): s is string => !!s);
  if (!candidates.length) return null;
  // Pick the latest by actual instant, not lex compare.
  candidates.sort((a, b) => Date.parse(a) - Date.parse(b));
  return candidates[candidates.length - 1];
}

export async function setLastCronRun(db: D1Database): Promise<void> {
  // Stored as strict UTC ISO 8601 with Z, so getLastUpdateTime can hand
  // it to the browser as a Date string that's parsed unambiguously.
  const now = new Date().toISOString();
  await db
    .prepare(
      `INSERT INTO kv_store (key, value, updated_at)
       VALUES ('last_cron_run', ?, datetime('now'))
       ON CONFLICT(key) DO UPDATE SET
         value = excluded.value,
         updated_at = excluded.updated_at`,
    )
    .bind(now)
    .run();
}

export async function getMarketOverviewRows(
  db: D1Database,
  symbols?: string[],
): Promise<Record<string, unknown>[]> {
  if (symbols && symbols.length > 0) {
    const placeholders = symbols.map(() => "?").join(",");
    const rows = await db
      .prepare(
        `SELECT symbol, name, as_of, close, chg_1w_pct, chg_1m_pct, chg_3m_pct, chg_1y_pct, source_url
         FROM market_overview WHERE lower(symbol) IN (${placeholders})`,
      )
      .bind(...symbols.map((s) => s.toLowerCase()))
      .all<Record<string, unknown>>();
    return rows.results;
  }
  const rows = await db
    .prepare(
      `SELECT symbol, name, as_of, close, chg_1w_pct, chg_1m_pct, chg_3m_pct, chg_1y_pct, source_url
       FROM market_overview ORDER BY symbol`,
    )
    .all<Record<string, unknown>>();
  return rows.results;
}

export async function upsertMarketOverviewRows(
  db: D1Database,
  rows: Record<string, unknown>[],
): Promise<void> {
  if (!rows.length) return;
  const now = new Date().toISOString().replace("T", " ").slice(0, 19) + "Z";
  const stmts = rows.map((r) =>
    db
      .prepare(
        `INSERT INTO market_overview
           (symbol, name, as_of, close, chg_1w_pct, chg_1m_pct, chg_3m_pct, chg_1y_pct, source_url, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(symbol) DO UPDATE SET
           name=excluded.name, as_of=excluded.as_of, close=excluded.close,
           chg_1w_pct=excluded.chg_1w_pct, chg_1m_pct=excluded.chg_1m_pct,
           chg_3m_pct=excluded.chg_3m_pct, chg_1y_pct=excluded.chg_1y_pct,
           source_url=excluded.source_url, updated_at=excluded.updated_at`,
      )
      .bind(
        r.symbol, r.name, r.as_of, r.close,
        r.chg_1w_pct ?? null, r.chg_1m_pct ?? null,
        r.chg_3m_pct ?? null, r.chg_1y_pct ?? null,
        r.source_url ?? null, now,
      ),
  );
  await db.batch(stmts);
}

export async function getNewsCacheEntry(
  db: D1Database,
  cacheKey: string,
  asOf: string,
  maxAgeSeconds = 86400,
): Promise<unknown[] | null> {
  const row = await db
    .prepare(`SELECT payload_json, fetched_at FROM news_cache WHERE cache_key=? AND as_of=?`)
    .bind(cacheKey, asOf)
    .first<{ payload_json: string; fetched_at: string }>();
  if (!row) return null;
  const age = (Date.now() - new Date(row.fetched_at).getTime()) / 1000;
  if (age > maxAgeSeconds) return null;
  try {
    return JSON.parse(row.payload_json) as unknown[];
  } catch {
    return null;
  }
}

export async function upsertNewsCache(
  db: D1Database,
  cacheKey: string,
  asOf: string,
  payload: unknown[],
): Promise<void> {
  const now = new Date().toISOString();
  await db
    .prepare(
      `INSERT INTO news_cache (cache_key, as_of, payload_json, fetched_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(cache_key, as_of) DO UPDATE SET
         payload_json=excluded.payload_json, fetched_at=excluded.fetched_at`,
    )
    .bind(cacheKey, asOf, JSON.stringify(payload), now)
    .run();
}
