-- D1 database schema for Poor Trader Dashboard
-- Run with: wrangler d1 execute poor-trader-db --remote --file=./cloudflare/schema.sql

CREATE TABLE IF NOT EXISTS observations (
  indicator_id TEXT NOT NULL,
  as_of TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  source TEXT NOT NULL,
  meta_json TEXT,
  inserted_at TEXT NOT NULL,
  PRIMARY KEY (indicator_id, as_of)
);

CREATE TABLE IF NOT EXISTS market_overview (
  symbol TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  as_of TEXT NOT NULL,
  close REAL NOT NULL,
  chg_1w_pct REAL,
  chg_1m_pct REAL,
  chg_3m_pct REAL,
  chg_1y_pct REAL,
  source_url TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_cache (
  cache_key TEXT NOT NULL,
  as_of TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (cache_key, as_of)
);

CREATE TABLE IF NOT EXISTS kv_store (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
