"""
World Major Indices: metadata + price fetcher used by the World Map module.

Each entry pairs a stooq symbol (price source, free) with optional Finnhub
metadata (news_proxy/kw, see news.py). Coordinates are the (approximate)
financial-center lat/lng used to place a marker on the ECharts world map.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from .market import (
    _fetch_stooq_daily_closes,
    _fetch_stooq_quote,
    _fetch_yahoo_chart,
    _pct_change,
)


# stooq symbols use lowercase, Finnhub company-news symbols are upper-case ETFs.
# `lat`/`lng` are the marker locations on the world map (often offset slightly
# from the financial center so labels don't overlap each other).
WORLD_INDICES: list[dict[str, Any]] = [
    # ---- USA (3, all use US ETF proxies for company-news) ----
    {
        "stooq": "^spx", "yahoo": "^GSPC",
        "name": "S&P 500",
        "country": "United States",
        "iso": "USA",
        "lat": 38.9, "lng": -95.0,
        "news_proxy": "SPY",
        "kw": ["S&P", "SPX", "Wall Street", "U.S. stocks", "US stocks"],
    },
    {
        "stooq": "^dji", "yahoo": "^DJI",
        "name": "Dow Jones",
        "country": "United States",
        "iso": "USA",
        "lat": 32.5, "lng": -88.0,
        "news_proxy": "DIA",
        "kw": ["Dow", "DJIA", "Dow Jones"],
    },
    {
        "stooq": "^ndq", "yahoo": "^IXIC",
        "name": "Nasdaq",
        "country": "United States",
        "iso": "USA",
        "lat": 44.0, "lng": -89.0,
        "news_proxy": "QQQ",
        "kw": ["Nasdaq", "tech stocks", "QQQ"],
    },
    # ---- Europe ----
    {
        "stooq": "^ftm", "yahoo": "^FTSE",
        "name": "FTSE 100",
        "country": "United Kingdom",
        "iso": "GBR",
        "lat": 53.0, "lng": -2.0,
        "news_proxy": None,
        "kw": ["FTSE", "London stocks", "UK stocks", "British stocks"],
    },
    {
        "stooq": "^dax", "yahoo": "^GDAXI",
        "name": "DAX",
        "country": "Germany",
        "iso": "DEU",
        "lat": 52.0, "lng": 12.0,
        "news_proxy": None,
        "kw": ["DAX", "German stocks", "Germany stocks", "Frankfurt"],
    },
    {
        "stooq": "^cac", "yahoo": "^FCHI",
        "name": "CAC 40",
        "country": "France",
        "iso": "FRA",
        "lat": 46.5, "lng": 2.5,
        "news_proxy": None,
        "kw": ["CAC", "French stocks", "France stocks", "Paris"],
    },
    # ---- Developed Asia ----
    {
        "stooq": "^nkx", "yahoo": "^N225",
        "name": "Nikkei 225",
        "country": "Japan",
        "iso": "JPN",
        "lat": 38.0, "lng": 138.5,
        "news_proxy": None,
        "kw": ["Nikkei", "Japan stocks", "Tokyo stocks"],
    },
    {
        "stooq": "^hsi", "yahoo": "^HSI",
        "name": "Hang Seng",
        "country": "Hong Kong",
        "iso": "HKG",
        "lat": 22.5, "lng": 114.2,
        "news_proxy": None,
        "kw": ["Hang Seng", "Hong Kong stocks", "HSI"],
    },
    {
        "stooq": "^kospi", "yahoo": "^KS11",
        "name": "KOSPI",
        "country": "South Korea",
        "iso": "KOR",
        "lat": 36.5, "lng": 127.8,
        "news_proxy": None,
        "kw": ["Kospi", "South Korea stocks", "Korean stocks", "Seoul"],
    },
    {
        "stooq": "^xjo", "yahoo": "^AXJO",
        "name": "ASX 200",
        "country": "Australia",
        "iso": "AUS",
        "lat": -25.0, "lng": 134.0,
        "news_proxy": None,
        "kw": ["ASX", "Australia stocks", "Australian shares", "S&P/ASX"],
    },
    # ---- Emerging Asia ----
    {
        "stooq": "^shc", "yahoo": "000001.SS",
        "name": "Shanghai Composite",
        "country": "China",
        "iso": "CHN",
        "lat": 31.5, "lng": 118.0,
        "news_proxy": None,
        "kw": ["Shanghai", "China stocks", "Chinese stocks", "SSE"],
    },
    {
        "stooq": "^bsx", "yahoo": "^BSESN",
        "name": "Sensex",
        "country": "India",
        "iso": "IND",
        "lat": 22.0, "lng": 78.0,
        "news_proxy": None,
        "kw": ["Sensex", "India stocks", "Indian shares", "BSE"],
    },
    {
        "stooq": "^nse", "yahoo": "^NSEI",
        "name": "Nifty 50",
        "country": "India",
        "iso": "IND",
        "lat": 18.5, "lng": 78.5,
        "news_proxy": None,
        "kw": ["Nifty", "NSE", "India stocks", "Indian shares"],
    },
    {
        "stooq": "^twse", "yahoo": "^TWII",
        "name": "TWSE",
        "country": "Taiwan",
        "iso": "TWN",
        "lat": 24.0, "lng": 121.0,
        "news_proxy": None,
        "kw": ["Taiwan stocks", "Taipei stocks", "TWSE", "TAIEX"],
    },
    {
        "stooq": "^sti", "yahoo": "^STI",
        "name": "Singapore STI",
        "country": "Singapore",
        "iso": "SGP",
        "lat": 1.4, "lng": 103.8,
        "news_proxy": None,
        "kw": ["STI", "Singapore stocks", "Straits Times"],
    },
]


# Plausible last-known close + day-change values used when the live data source
# (stooq) refuses to serve us. Numbers are approximate snapshots from late 2026
# major-index quotes; they are obviously not real-time, but they let the world
# map render cleanly without empty markers.
SAMPLE_FALLBACK: dict[str, dict[str, float]] = {
    "^spx":   {"close": 5780.0,  "chg_1d_pct":  1.15},
    "^dji":   {"close": 42500.0, "chg_1d_pct":  1.38},
    "^ndq":   {"close": 18800.0, "chg_1d_pct":  1.38},
    "^ftm":   {"close": 8230.0,  "chg_1d_pct": -0.24},
    "^dax":   {"close": 19400.0, "chg_1d_pct":  1.22},
    "^cac":   {"close": 7480.0,  "chg_1d_pct":  0.79},
    "^nkx":   {"close": 39450.0, "chg_1d_pct":  1.43},
    "^hsi":   {"close": 21500.0, "chg_1d_pct":  2.62},
    "^kospi": {"close": 2610.0,  "chg_1d_pct":  0.51},
    "^xjo":   {"close": 8120.0,  "chg_1d_pct": -0.31},
    "^shc":   {"close": 3520.0,  "chg_1d_pct":  1.78},
    "^bsx":   {"close": 78050.0, "chg_1d_pct":  0.42},
    "^nse":   {"close": 23800.0, "chg_1d_pct":  0.38},
    "^twse":  {"close": 22450.0, "chg_1d_pct":  0.62},
    "^sti":   {"close": 3690.0,  "chg_1d_pct":  0.53},
}


def _sample_for(stooq_symbol: str) -> dict[str, float] | None:
    return SAMPLE_FALLBACK.get(stooq_symbol.lower())


def get_index_meta(stooq_symbol: str) -> dict[str, Any] | None:
    needle = (stooq_symbol or "").strip().lower()
    for it in WORLD_INDICES:
        if it["stooq"].lower() == needle:
            return it
    return None


def _fetch_one_overview(
    meta: dict[str, Any],
    *,
    session: requests.Session,
    history_days: int = 30,
) -> dict[str, Any]:
    """
    Compute the latest close + day-over-day % change for a single index.

    Strategy:
    - Pull the last ~30 days of daily closes from stooq.
    - Try the live quote endpoint; if it returns a date strictly newer than the
      latest daily row we treat that as the latest close. Otherwise we use the
      daily CSV's last row.
    - Day change = pct_change(latest, previous_day_close).
    """
    out: dict[str, Any] = {
        "stooq": meta["stooq"],
        "name": meta["name"],
        "country": meta["country"],
        "iso": meta["iso"],
        "lat": meta["lat"],
        "lng": meta["lng"],
        "close": None,
        "prev_close": None,
        "as_of": None,
        "chg_1d_pct": None,
        "ok": False,
        "is_sample": False,
    }
    end = date.today()
    start = end - timedelta(days=history_days)

    # 1) Try Yahoo Finance first (real, free, no auth, currently the most reliable).
    series: list[tuple[date, float]] = []
    yh = meta.get("yahoo")
    if yh:
        try:
            series = _fetch_yahoo_chart(yh, range_="3mo", interval="1d", session=session)
        except Exception:
            series = []

    # 2) Fallback to stooq daily CSV if Yahoo failed.
    if not series:
        try:
            series = _fetch_stooq_daily_closes(meta["stooq"], start=start, end=end, session=session)
        except Exception:
            series = []

    # 3) Last resort: synthetic sample data.
    if not series:
        sample = _sample_for(meta["stooq"])
        if sample:
            out.update(
                {
                    "close": sample["close"],
                    "prev_close": sample["close"] / (1.0 + sample["chg_1d_pct"] / 100.0)
                    if (1.0 + sample["chg_1d_pct"] / 100.0) != 0 else None,
                    "as_of": end.isoformat(),
                    "chg_1d_pct": sample["chg_1d_pct"],
                    "ok": True,
                    "is_sample": True,
                }
            )
        return out

    as_of, last_close = series[-1]
    closes = [c for _, c in series]

    # Stooq quote endpoint sometimes has a fresher intraday close than its
    # daily CSV. Yahoo's chart already includes today, so only consult stooq
    # quote when we *fell back* to stooq daily history.
    if not yh or len(series) < 2:
        try:
            q = _fetch_stooq_quote(meta["stooq"], session=session)
        except Exception:
            q = None
        if q is not None:
            qd, qc = q
            if qd > as_of:
                as_of, last_close = qd, qc
                closes.append(qc)
            elif qd == as_of:
                as_of, last_close = qd, qc
                closes[-1] = qc

    if len(closes) < 2:
        sample = _sample_for(meta["stooq"])
        if sample:
            out.update(
                {
                    "close": last_close,
                    "prev_close": last_close / (1.0 + sample["chg_1d_pct"] / 100.0)
                    if (1.0 + sample["chg_1d_pct"] / 100.0) != 0 else None,
                    "as_of": as_of.isoformat(),
                    "chg_1d_pct": sample["chg_1d_pct"],
                    "ok": True,
                    "is_sample": True,
                }
            )
        return out

    prev = closes[-2]
    chg = _pct_change(last_close, prev)

    out.update(
        {
            "close": last_close,
            "prev_close": prev,
            "as_of": as_of.isoformat(),
            "chg_1d_pct": chg,
            "ok": True,
            "is_sample": False,
        }
    )
    return out


def get_world_overview(*, db_path: str | Path | None = None, with_news: bool = True) -> list[dict[str, Any]]:
    """
    Returns one row per world index (price + day change + up to 3 headlines).
    News fetch is skipped silently when FINNHUB_KEY is not set.
    """
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(WORLD_INDICES))) as ex:
        futs = {ex.submit(_fetch_one_overview, m, session=session): m for m in WORLD_INDICES}
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                r = fut.result()
            except Exception:
                sample = _sample_for(m["stooq"])
                r = {
                    "stooq": m["stooq"],
                    "name": m["name"],
                    "country": m["country"],
                    "iso": m["iso"],
                    "lat": m["lat"],
                    "lng": m["lng"],
                    "close": sample["close"] if sample else None,
                    "prev_close": None,
                    "as_of": date.today().isoformat() if sample else None,
                    "chg_1d_pct": sample["chg_1d_pct"] if sample else None,
                    "ok": bool(sample),
                    "is_sample": bool(sample),
                }
            r["headlines"] = []
            rows.append(r)

    if with_news:
        # News fetch is best-effort and uses cached data when possible.
        try:
            from .news import fetch_news_for_index, is_enabled

            if is_enabled():
                for r in rows:
                    if not r.get("ok") or r.get("is_sample"):
                        continue
                    try:
                        target = date.fromisoformat(r["as_of"])
                    except Exception:
                        target = date.today()
                    meta = get_index_meta(r["stooq"]) or {}
                    try:
                        articles = fetch_news_for_index(
                            meta, target, db_path=db_path, limit=3
                        )
                    except Exception:
                        articles = []
                    r["headlines"] = articles
        except Exception:
            pass

    # Stable ordering: by WORLD_INDICES declaration order.
    order = {m["stooq"].lower(): i for i, m in enumerate(WORLD_INDICES)}
    rows.sort(key=lambda x: order.get(str(x.get("stooq", "")).lower(), 999))
    return rows


def _generate_sample_series(
    stooq_symbol: str,
    *,
    days: int,
) -> list[tuple[date, float]]:
    """
    Build a deterministic synthetic price series for indices that stooq won't
    serve. The series ends today at SAMPLE_FALLBACK[stooq]['close'] and walks
    backwards with a small daily drift + noise; it's clearly *sample* data and
    flagged as such in the API response, but it lets the trend chart and
    significant-move pin annotations render something useful.
    """
    import random as _random

    sample = _sample_for(stooq_symbol)
    if not sample:
        return []
    # Seed by symbol so reloads don't keep redrawing different histories.
    rng = _random.Random(hash(stooq_symbol) & 0xFFFFFFFF)
    end = date.today()
    out: list[tuple[date, float]] = []
    last = float(sample["close"])
    cur = end
    out.append((cur, last))
    for _ in range(days - 1):
        # 1.0% stdev daily, slight long-term mean reversion via 0.001 drift.
        step = rng.gauss(-0.0005, 0.011)
        last = last / (1.0 + step)
        cur = cur - timedelta(days=1)
        out.append((cur, max(last, 0.01)))
    out.reverse()  # chronological order
    return out


def get_index_history(
    stooq_symbol: str,
    range_key: str,
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Build the index detail series + significant-move annotations.

    range_key:
      - "1m": last ~30 days
      - "1y": last ~365 days
      - "all": last ~10 years (capped at stooq's history)

    A "significant" day is one whose |daily % change| is in the top 6 of the
    range AND >= max(1.5%, 1.5 * stdev). We cap the result at 8 markers.
    Each significant day is annotated with up to 3 news articles.
    """
    meta = get_index_meta(stooq_symbol)
    if not meta:
        return {"series": [], "significant": [], "name": None, "stooq": stooq_symbol}

    days_map = {"1m": 45, "1y": 400, "all": 3650}
    span = days_map.get(range_key.lower(), 400)
    end = date.today()
    start = end - timedelta(days=span + 30)  # +buffer for holidays/weekends
    session = requests.Session()

    yahoo_range = {"1m": "1mo", "1y": "1y", "all": "10y"}.get(range_key.lower(), "1y")
    raw: list[tuple[date, float]] = []
    yh = meta.get("yahoo")
    if yh:
        try:
            raw = _fetch_yahoo_chart(yh, range_=yahoo_range, interval="1d", session=session)
        except Exception:
            raw = []
    if len(raw) < 5:
        try:
            raw = _fetch_stooq_daily_closes(meta["stooq"], start=start, end=end, session=session)
        except Exception:
            raw = []

    is_sample = False
    if len(raw) < 5:
        sample_days = {"1m": 30, "1y": 252, "all": 1500}.get(range_key.lower(), 252)
        raw = _generate_sample_series(meta["stooq"], days=sample_days)
        is_sample = bool(raw)

    # Trim back to roughly the requested span.
    if range_key == "1m":
        raw = raw[-30:] if len(raw) > 30 else raw
    elif range_key == "1y":
        raw = raw[-252:] if len(raw) > 252 else raw

    series: list[dict[str, Any]] = []
    pct_changes: list[float | None] = [None]
    closes = [c for _, c in raw]
    for i, (d, c) in enumerate(raw):
        chg = None
        if i > 0:
            chg = _pct_change(c, closes[i - 1])
            pct_changes.append(chg)
        series.append({"date": d.isoformat(), "close": c, "chg_pct": chg})

    significant: list[dict[str, Any]] = []
    if len(series) >= 5:
        valid = [(i, abs(p["chg_pct"])) for i, p in enumerate(series) if p["chg_pct"] is not None]
        if valid:
            sorted_by_abs = sorted(valid, key=lambda t: t[1], reverse=True)
            top_n_idx = {i for i, _ in sorted_by_abs[:6]}

            # 1.5 * stdev gate
            vals = [v for _, v in valid]
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
            sd = var ** 0.5
            gate = max(1.5, 1.5 * sd)

            chosen_idx: list[int] = []
            for i, p in enumerate(series):
                if p["chg_pct"] is None:
                    continue
                if i in top_n_idx and abs(p["chg_pct"]) >= gate:
                    chosen_idx.append(i)
            # If the gate filters everything (very flat range), keep top 3 by abs.
            if not chosen_idx:
                chosen_idx = [i for i, _ in sorted_by_abs[:3]]
            chosen_idx.sort()
            chosen_idx = chosen_idx[:8]

            chosen_dates = [date.fromisoformat(series[i]["date"]) for i in chosen_idx]
            news_by_date: dict[str, list[dict[str, Any]]] = {}
            try:
                from .news import fetch_news_for_range, is_enabled

                if is_enabled() and chosen_dates:
                    news_by_date = fetch_news_for_range(
                        meta, chosen_dates, db_path=db_path, per_day_limit=3
                    )
            except Exception:
                news_by_date = {}

            for i in chosen_idx:
                p = series[i]
                d = p["date"]
                significant.append(
                    {
                        "date": d,
                        "close": p["close"],
                        "chg_pct": p["chg_pct"],
                        "news": news_by_date.get(d, []),
                    }
                )

    return {
        "stooq": meta["stooq"],
        "name": meta["name"],
        "country": meta["country"],
        "range": range_key,
        "series": series,
        "significant": significant,
        "is_sample": is_sample,
    }
