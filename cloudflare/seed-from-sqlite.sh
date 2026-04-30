#!/usr/bin/env bash
# Export existing trader_alerts.sqlite3 data to Cloudflare D1.
# Run from the project root:
#   bash cloudflare/seed-from-sqlite.sh

set -e

DB="${1:-trader_alerts.sqlite3}"
DUMP="cloudflare/seed-dump.sql"
D1_NAME="poor-trader-db"

if [ ! -f "$DB" ]; then
  echo "ERROR: $DB not found. Run from the project root."
  exit 1
fi

echo "→ Dumping observations and market_overview from $DB..."
sqlite3 "$DB" <<'SQL' > "$DUMP"
.mode insert observations
SELECT indicator_id, as_of, value, unit, source, meta_json, inserted_at FROM observations;
.mode insert market_overview
SELECT symbol, name, as_of, close, chg_1w_pct, chg_1m_pct, chg_3m_pct, chg_1y_pct, source_url, updated_at FROM market_overview;
SQL

# Strip SQLite-specific pragma lines that D1 doesn't support
sed -i.bak '/^PRAGMA/d' "$DUMP"
sed -i.bak '/^BEGIN/d' "$DUMP"
sed -i.bak '/^COMMIT/d' "$DUMP"
rm -f "${DUMP}.bak"

echo "→ Creating D1 schema..."
npx wrangler d1 execute "$D1_NAME" --remote --file=cloudflare/schema.sql

echo "→ Seeding D1 from $DUMP..."
npx wrangler d1 execute "$D1_NAME" --remote --file="$DUMP"

echo "Done. Check row count:"
npx wrangler d1 execute "$D1_NAME" --remote --command="SELECT COUNT(*) FROM observations;"
