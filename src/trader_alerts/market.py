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


def get_us_index_overview_rows(extra_symbols: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Output dict rows for template use.

    1 week/month/3 months/1 year:
    - Approximate by "trading day count": 1W=5T, 1M=21T, 3M=63T, 1Y=252T
    """
    end = date.today()
    start = end - timedelta(days=900)  # Enough to cover 252 trading days + holiday buffer
    session = requests.Session()

    # Stooq symbols: indices, stocks, bitcoin, gold, silver
    index_items = [
        ("^spx", "^SPX"),
        ("^dji", "^DJI"),
        ("^ndq", "^NDQ"),
    ]
    asset_items = [
        ("BTC.V", "BTC"),
        ("XAUUSD", "XAU"),
        ("XAGUSD", "XAG"),
    ]
    stock_items = [
        ("BRK-B.US", "BRK-B"),
        ("KO.US", "KO"),
        ("RKLB.US", "RKLB"),
        ("AMZN.US", "AMZN"),
    ]

    extra_items: list[tuple[str, str]] = []
    for raw in extra_symbols or []:
        norm = _normalize_stock_symbol(raw)
        if norm:
            extra_items.append(norm)

    seen = {sym.lower() for sym, _ in (index_items + asset_items + stock_items)}
    deduped_extra = []
    for sym, name in extra_items:
        if sym.lower() in seen:
            continue
        seen.add(sym.lower())
        deduped_extra.append((sym, name))

    items = index_items + asset_items + stock_items + deduped_extra

    def _fetch_one(sym: str, name: str) -> dict[str, Any] | None:
        series = _fetch_stooq_daily_closes(sym, start=start, end=end, session=session)
        if not series:
            return None

        # 用 quote 的最新日期/最新收盘价（通常更新到最近一个交易日），避免 daily CSV 停留在更旧日期
        quote = None
        try:
            quote = _fetch_stooq_quote(sym, session=session)
        except Exception:
            quote = None

        as_of, last_close = series[-1]
        closes = [c for _, c in series]
        if quote is not None:
            qd, qc = quote
            if qd > as_of:
                # daily 还没更新到 qd，把 quote 作为最新一根补到末尾
                as_of, last_close = qd, qc
                closes.append(qc)
            elif qd == as_of:
                # 同一天：用 quote 的 close 覆盖，避免日线数据延迟/误差
                as_of, last_close = qd, qc
                closes[-1] = qc

        def chg(n_trading_days: int) -> float | None:
            idx = len(closes) - 1 - n_trading_days
            if idx < 0:
                return None
            return _pct_change(last_close, closes[idx])

        row = IndexOverviewRow(
            symbol=sym,
            name=name,
            as_of=as_of.strftime("%m-%d"),  # Only show month-day, no year
            close=last_close,
            chg_1w_pct=chg(5),
            chg_1m_pct=chg(21),
            chg_3m_pct=chg(63),
            chg_1y_pct=chg(252),
            source_url=f"https://stooq.com/q/l/?s={sym}",
        )
        return asdict(row)

    # 并发抓取：任何一个 symbol 慢/挂都不应拖死整块面板
    out: list[dict[str, Any]] = []
    max_workers = min(8, max(1, len(items)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_fetch_one, sym, name): (sym, name) for sym, name in items}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception:
                row = None
            if row:
                out.append(row)

    return out


