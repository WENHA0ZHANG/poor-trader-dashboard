"""
Indicator history backfill from public, unauthenticated sources.

This module is run once on app startup (in a background thread) to seed
the SQLite store with as much historical context as we can pull for free,
so the "Indicator Trends" chart is meaningful even on a freshly-deployed
instance (e.g., on Render where there is no persisted DB yet).

Sources used (all public, no auth):

    sp500_rsi             Wilder RSI(14) computed from ^GSPC daily closes (Yahoo)
                          - matches the public investing.com daily RSI value
    vix                   Yahoo Finance ^VIX daily close
    cnn_fear_greed_index  CNN dataviz graphdata.fear_and_greed_historical
    cnn_put_call_options  CNN dataviz graphdata.put_call_options
    us_high_yield_spread  FRED public CSV BAMLH0A0HYM2 (in %, stored as bp)
    sp500_pe_ratio        multpl.com /by-month HTML table
    cboe_skew             Yahoo Finance ^SKEW daily close (NEW indicator)
    yc_10y_2y             FRED public CSV T10Y2Y (NEW indicator)

All upserts are idempotent on (indicator_id, as_of). Repeated runs only
update the same rows.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta

import requests

from .constants import IndicatorId
from .market import _fetch_yahoo_chart
from .models import Observation
from .providers.cnn import CnnFearGreedProvider
from .providers.sp500_rsi import compute_wilder_rsi
from .storage import upsert_observations


# ---------- generic helpers ----------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _http_get(url: str, *, headers: dict[str, str] | None = None,
              session: requests.Session | None = None,
              timeout: tuple[float, float] = (5.0, 25.0)) -> str | None:
    """
    Robust GET. (connect_timeout, read_timeout) tuple. Retries once on
    connection / read errors because some public CSV endpoints (notably
    fred.stlouisfed.org) intermittently take 10+s to first byte under
    the default urllib3 connection-pool keep-alive.
    """
    s = session or requests.Session()
    h = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",  # avoid keep-alive socket reuse with FRED
    }
    if headers:
        h.update(headers)
    last_err: Exception | None = None
    for _ in range(2):
        try:
            r = s.get(url, headers=h, timeout=timeout)
            if r.status_code >= 400:
                return None
            return r.text or ""
        except Exception as e:
            last_err = e
    return None


def _fetch_fred_csv(series_id: str, *, start: date | None = None,
                    session: requests.Session | None = None) -> list[tuple[date, float]]:
    """
    Pull a FRED series as CSV via the public graph endpoint (no API key).

    Format:
        observation_date,SERIES_ID
        2023-01-03,4.53
        ...
        2026-04-29,3.27

    Note on UA: fred.stlouisfed.org significantly slow-walks browser-style
    User-Agents (multi-second TTFB and frequent ReadTimeouts) but responds
    in <1s to simple non-browser UAs like curl/wget. We override here.
    """
    if start is None:
        start = date.today() - timedelta(days=365 * 5 + 30)
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd={start.isoformat()}"
    )
    text = _http_get(
        url,
        session=session,
        headers={"User-Agent": "curl/8.4.0", "Accept": "text/csv,*/*"},
        timeout=(5.0, 15.0),
    )
    if not text:
        return []

    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or len(header) < 2:
        return []
    out: list[tuple[date, float]] = []
    for row in reader:
        if len(row) < 2:
            continue
        try:
            d = date.fromisoformat(row[0])
            v = float(row[1])
        except (ValueError, TypeError):
            continue
        out.append((d, v))
    return out


# ---------- per-indicator builders ---------------------------------------

def _backfill_rsi_from_gspc(session: requests.Session) -> list[Observation]:
    """Wilder RSI(14) computed from ^GSPC daily closes."""
    try:
        series = _fetch_yahoo_chart("^GSPC", range_="1y", interval="1d", session=session)
    except Exception:
        return []
    if len(series) < 20:
        return []
    closes = [c for _, c in series]
    out: list[Observation] = []
    for end_idx in range(15, len(closes)):
        rsi = compute_wilder_rsi(closes[: end_idx + 1], period=14)
        if rsi is None:
            continue
        out.append(
            Observation(
                indicator_id=IndicatorId.SP500_RSI,
                as_of=series[end_idx][0],
                value=round(rsi, 2),
                unit="0-100",
                source="Investing.com",
                meta={"method": "Wilder RSI(14) from ^GSPC daily closes (Yahoo)"},
            )
        )
    return out


def _backfill_vix(session: requests.Session) -> list[Observation]:
    try:
        series = _fetch_yahoo_chart("^VIX", range_="1y", interval="1d", session=session)
    except Exception:
        return []
    return [
        Observation(
            indicator_id=IndicatorId.VIX,
            as_of=d,
            value=round(float(v), 2),
            unit="index",
            source="Yahoo Finance",
            meta={"symbol": "^VIX"},
        )
        for d, v in series
    ]


def _backfill_skew(session: requests.Session) -> list[Observation]:
    """CBOE SKEW Index daily close (tail-risk pricing). Higher = more tail-hedging."""
    try:
        series = _fetch_yahoo_chart("^SKEW", range_="1y", interval="1d", session=session)
    except Exception:
        return []
    return [
        Observation(
            indicator_id=IndicatorId.CBOE_SKEW,
            as_of=d,
            value=round(float(v), 2),
            unit="index",
            source="CBOE / Yahoo Finance",
            meta={"symbol": "^SKEW"},
        )
        for d, v in series
    ]


def _backfill_hy_oas(session: requests.Session) -> list[Observation]:
    """
    FRED BAMLH0A0HYM2 — ICE BofA US High Yield Index Option-Adjusted Spread.
    Returned in percent; the rest of the codebase stores HY in bp.
    """
    series = _fetch_fred_csv("BAMLH0A0HYM2", session=session)
    return [
        Observation(
            indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
            as_of=d,
            value=round(float(v) * 100.0, 1),  # % -> bp
            unit="bp",
            source="FRED:BAMLH0A0HYM2",
            meta={"url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"},
        )
        for d, v in series
    ]


def _backfill_yc_10y2y(session: requests.Session) -> list[Observation]:
    """FRED T10Y2Y — 10Y minus 2Y Treasury yield (in %). Inversion <0 = recession risk."""
    series = _fetch_fred_csv("T10Y2Y", session=session)
    return [
        Observation(
            indicator_id=IndicatorId.YC_10Y_2Y,
            as_of=d,
            value=round(float(v), 3),
            unit="%",
            source="FRED:T10Y2Y",
            meta={"url": "https://fred.stlouisfed.org/series/T10Y2Y"},
        )
        for d, v in series
    ]


def _backfill_cnn(session: requests.Session) -> list[Observation]:
    """
    CNN graphdata returns ~1y of daily history for fear-and-greed and put/call.
    """
    out: list[Observation] = []
    try:
        provider = CnnFearGreedProvider(session=session)
        data = provider._fetch_graphdata()
    except Exception:
        return out

    fg_hist = (data.get("fear_and_greed_historical") or {}).get("data") or []
    for pt in fg_hist:
        try:
            ts_ms = float(pt["x"])
            value = float(pt["y"])
            d = datetime.utcfromtimestamp(ts_ms / 1000.0).date()
        except Exception:
            continue
        out.append(
            Observation(
                indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
                as_of=d,
                value=round(value, 2),
                unit="0-100",
                source="CNN:dataviz",
                meta={"rating": pt.get("rating"), "url": provider.URL},
            )
        )

    pc_hist = (data.get("put_call_options") or {}).get("data") or []
    for pt in pc_hist:
        try:
            ts_ms = float(pt["x"])
            value = float(pt["y"])
            d = datetime.utcfromtimestamp(ts_ms / 1000.0).date()
        except Exception:
            continue
        out.append(
            Observation(
                indicator_id=IndicatorId.CNN_PUT_CALL_OPTIONS,
                as_of=d,
                value=round(value, 4),
                unit="ratio",
                source="CNN:dataviz",
                meta={"rating": pt.get("rating"), "url": provider.URL},
            )
        )
    return out


_MULTPL_ROW_RE = re.compile(
    r"<tr[^>]*>\s*"
    r"<td[^>]*>\s*([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s*</td>\s*"
    r"<td[^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)
_MULTPL_VALUE_RE = re.compile(r"([0-9]+\.[0-9]+)")


def fetch_multpl_pe_monthly(session: requests.Session | None = None) -> dict[date, float]:
    """
    Pull the S&P 500 PE Ratio monthly table from multpl.com.

    Returns a {date: pe} dict (one row per calendar month, ~150+ years of history).
    Used both for backfilling history into SQLite and for computing the
    "historical percentile" hint in compute_signals.
    """
    text = _http_get(
        "https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
        session=session,
    )
    if not text:
        return {}

    out: dict[date, float] = {}
    for raw_date, value_cell in _MULTPL_ROW_RE.findall(text):
        # The PE value cell may contain HTML entities (e.g. &#x2002;), an
        # optional <abbr>† Estimate</abbr> marker, and the actual number.
        # The first decimal-number-with-a-dot in the cell is the PE.
        m = _MULTPL_VALUE_RE.search(value_cell)
        if not m:
            continue
        try:
            d = datetime.strptime(raw_date.strip(), "%b %d, %Y").date()
            v = float(m.group(1))
        except ValueError:
            continue
        out[d] = v
    return out


def _backfill_sp500_pe(session: requests.Session) -> list[Observation]:
    table = fetch_multpl_pe_monthly(session=session)
    # Keep ~10 years of monthly history – enough for the trend chart, but small enough
    # to avoid blowing up the sqlite file with century-old data points.
    cutoff = date.today() - timedelta(days=365 * 10 + 60)
    return [
        Observation(
            indicator_id=IndicatorId.SP500_PE_RATIO,
            as_of=d,
            value=round(float(v), 2),
            unit="x",
            source="multpl.com",
            meta={"url": "https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
                  "frequency": "monthly"},
        )
        for d, v in sorted(table.items()) if d >= cutoff
    ]


# ---------- public entry point -------------------------------------------

def backfill_history(db_path: str) -> dict[str, int]:
    """
    Run all backfill jobs and upsert the results.

    Returns {indicator_id_value: rows_written} for diagnostics.
    """
    session = requests.Session()
    written: dict[str, int] = {}

    jobs = [
        ("sp500_rsi",            _backfill_rsi_from_gspc),
        ("vix",                  _backfill_vix),
        ("cboe_skew",            _backfill_skew),
        ("us_high_yield_spread", _backfill_hy_oas),
        ("yc_10y_2y",            _backfill_yc_10y2y),
        ("sp500_pe_ratio",       _backfill_sp500_pe),
        # cnn returns observations for both indicators in one call
        ("cnn",                  _backfill_cnn),
    ]
    for tag, fn in jobs:
        try:
            obs = fn(session)
        except Exception:
            obs = []
        if not obs:
            continue
        try:
            n = upsert_observations(db_path, obs)
            # Group "cnn" job into separate counters per indicator id
            if tag == "cnn":
                fg = sum(1 for o in obs if o.indicator_id == IndicatorId.CNN_FEAR_GREED_INDEX)
                pc = sum(1 for o in obs if o.indicator_id == IndicatorId.CNN_PUT_CALL_OPTIONS)
                written["cnn_fear_greed_index"] = fg
                written["cnn_put_call_options"] = pc
            else:
                written[tag] = n
        except Exception:
            pass
    return written
