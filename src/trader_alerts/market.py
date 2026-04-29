from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass(frozen=True)
class IndexOverviewRow:
    symbol: str
    name: str
    as_of: date
    close: float
    chg_1w_pct: float | None
    chg_1m_pct: float | None
    chg_3m_pct: float | None
    chg_1y_pct: float | None
    source_url: str


def _pct_change(last: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (last / prev - 1.0) * 100.0


def _fetch_stooq_quote(
    symbol: str,
    *,
    session: requests.Session | None = None,
) -> tuple[date, float] | None:
    """
    Stooq quote CSV（通常比 daily candles 更新更快）：
    - https://stooq.com/q/l/?s=^spx&f=sd2t2ohlcv&h&e=csv
    """
    url = "https://stooq.com/q/l/"
    params = {"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"}
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"}
    s = session or requests.Session()
    resp = s.get(url, params=params, headers=headers, timeout=(2, 6))
    resp.raise_for_status()
    text = (resp.text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    # Symbol,Date,Time,Open,High,Low,Close,Volume
    parts = lines[1].split(",")
    if len(parts) < 7:
        return None
    d = date.fromisoformat(parts[1])
    c = float(parts[6])
    return (d, c)


def _fetch_stooq_daily_closes(
    symbol: str,
    *,
    start: date,
    end: date,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = (2, 6),
) -> list[tuple[date, float]]:
    """
    Stooq CSV：
    - https://stooq.com/q/d/l/?s=^spx&i=d&d1=20240101&d2=20251231
    """
    url = "https://stooq.com/q/d/l/"
    params = {
        "s": symbol,
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"}
    s = session or requests.Session()
    # Dashboard real-time display, avoid long blocking
    resp = s.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text or text.lower().startswith("no data"):
        return []

    rows: list[tuple[date, float]] = []
    lines = text.splitlines()
    # Date,Open,High,Low,Close,Volume
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 5:
            continue
        d = date.fromisoformat(parts[0])
        c = float(parts[4])
        rows.append((d, c))
    return rows


def _fetch_yahoo_chart(
    symbol: str,
    *,
    range_: str = "1y",
    interval: str = "1d",
    session: requests.Session | None = None,
    timeout: tuple[float, float] = (3, 8),
) -> list[tuple[date, float]]:
    """
    Yahoo Finance chart API (no auth, free):
        https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?range=1y&interval=1d

    Returns chronological [(date, close), ...]. Skips entries where close is None
    (Yahoo emits null for trading holidays/halts mid-series).
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": range_, "interval": interval, "includePrePost": "false"}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
    }
    s = session or requests.Session()
    resp = s.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return []
        r0 = result[0]
        ts = r0.get("timestamp") or []
        quote = (r0.get("indicators") or {}).get("quote") or []
        if not ts or not quote:
            return []
        closes = quote[0].get("close") or []
    except Exception:
        return []

    from datetime import datetime as _dt, timezone as _tz

    out: list[tuple[date, float]] = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        try:
            d = _dt.fromtimestamp(int(t), tz=_tz.utc).date()
        except Exception:
            continue
        out.append((d, float(c)))
    return out


def _normalize_stock_symbol(raw: str) -> tuple[str, str] | None:
    s = (raw or "").strip().upper().replace(" ", "")
    if not s:
        return None
    # Drop .US suffix if present and normalize dots to dashes
    if s.endswith(".US"):
        s = s[:-3]
    s = s.replace(".", "-")
    # Allow letters, numbers, and dashes only
    if not all(c.isalnum() or c == "-" for c in s):
        return None
    return (f"{s}.US", s)


_DEFAULT_ITEMS: list[dict[str, str]] = [
    # symbol = legacy stooq id (used as the row key on the front-end);
    # yahoo  = corresponding Yahoo Finance ticker (primary live source).
    {"symbol": "^spx",      "yahoo": "^GSPC",   "name": "^SPX"},
    {"symbol": "^dji",      "yahoo": "^DJI",    "name": "^DJI"},
    {"symbol": "^ndq",      "yahoo": "^IXIC",   "name": "^NDQ"},
    {"symbol": "btc.v",     "yahoo": "BTC-USD", "name": "BTC"},
    {"symbol": "xauusd",    "yahoo": "GC=F",    "name": "XAU"},
    {"symbol": "xagusd",    "yahoo": "SI=F",    "name": "XAG"},
    {"symbol": "brk-b.us",  "yahoo": "BRK-B",   "name": "BRK-B"},
    {"symbol": "ko.us",     "yahoo": "KO",      "name": "KO"},
    {"symbol": "rklb.us",   "yahoo": "RKLB",    "name": "RKLB"},
    {"symbol": "amzn.us",   "yahoo": "AMZN",    "name": "AMZN"},
]


def get_us_index_overview_rows(extra_symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Live overview rows for the front-end's three market tables.

    Primary source: Yahoo Finance chart API (free, no auth, decent uptime). The
    legacy stooq path is used only as a fallback because stooq's daily-CSV
    endpoint now requires an apikey, which makes it unreliable from cloud
    hosts (e.g., Render).
    """
    end = date.today()
    start = end - timedelta(days=900)  # Enough for 252 trading days + holiday buffer
    session = requests.Session()

    items: list[dict[str, str]] = list(_DEFAULT_ITEMS)
    seen = {it["symbol"].lower() for it in items}

    for raw in extra_symbols or []:
        norm = _normalize_stock_symbol(raw)
        if not norm:
            continue
        legacy_sym, ticker = norm  # ("AAPL.US", "AAPL")
        if legacy_sym.lower() in seen:
            continue
        seen.add(legacy_sym.lower())
        items.append({"symbol": legacy_sym.lower(), "yahoo": ticker, "name": ticker})

    def _fetch_one(it: dict[str, str]) -> dict[str, Any] | None:
        legacy_sym = it["symbol"]
        yh = it["yahoo"]
        name = it["name"]

        series: list[tuple[date, float]] = []
        # Yahoo first.
        try:
            series = _fetch_yahoo_chart(yh, range_="2y", interval="1d", session=session)
        except Exception:
            series = []

        # Stooq fallback.
        if not series:
            try:
                series = _fetch_stooq_daily_closes(legacy_sym, start=start, end=end, session=session)
            except Exception:
                series = []
            try:
                quote = _fetch_stooq_quote(legacy_sym, session=session)
            except Exception:
                quote = None
            if series and quote is not None:
                qd, qc = quote
                if qd > series[-1][0]:
                    series.append((qd, qc))
                elif qd == series[-1][0]:
                    series[-1] = (qd, qc)

        if not series or len(series) < 2:
            return None

        as_of, last_close = series[-1]
        closes = [c for _, c in series]

        def chg(n_trading_days: int) -> float | None:
            idx = len(closes) - 1 - n_trading_days
            if idx < 0:
                return None
            return _pct_change(last_close, closes[idx])

        row = IndexOverviewRow(
            symbol=legacy_sym,
            name=name,
            as_of=as_of.strftime("%m-%d"),
            close=last_close,
            chg_1w_pct=chg(5),
            chg_1m_pct=chg(21),
            chg_3m_pct=chg(63),
            chg_1y_pct=chg(252),
            source_url=f"https://finance.yahoo.com/quote/{yh}",
        )
        return asdict(row)

    # Concurrent fetch: don't let one slow symbol stall the whole panel.
    out: list[dict[str, Any]] = []
    max_workers = min(8, max(1, len(items)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_one, it): it for it in items}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row:
                out.append(row)

    return out


