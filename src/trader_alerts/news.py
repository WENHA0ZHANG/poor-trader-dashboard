"""
Finnhub-backed news fetching for the World Indices map and significant-move
annotations on the Index Detail panel.

Free tier endpoints used:
- /company-news?symbol={SPY|DIA|QQQ}&from=YYYY-MM-DD&to=YYYY-MM-DD
- /news?category=general

Set the FINNHUB_KEY environment variable to enable. Without a key, all functions
return empty lists -- the rest of the app degrades gracefully.

Results are cached in the SQLite news_cache table (see storage.py) for 24h to
keep us well under the 60-rpm free-tier rate limit.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

from .storage import get_cached_news, upsert_cached_news


_FINNHUB_BASE = "https://finnhub.io/api/v1"
_DEFAULT_TIMEOUT: tuple[float, float] = (3, 8)
_NEWS_CACHE_TTL_SECONDS = 24 * 3600


_KEY_FILES = ("finnhub_key.txt", ".finnhub_key", "secrets/finnhub_key.txt")


def _get_api_key() -> str | None:
    """
    Resolve the Finnhub API key. Order:
      1. FINNHUB_KEY env var
      2. finnhub_key.txt / .finnhub_key / secrets/finnhub_key.txt in CWD
      3. Same files relative to the project root (one level above the package).

    Anything containing whitespace, comments, or quotes is stripped so users can
    paste the raw key on the first line of a text file without ceremony.
    """
    env = (os.environ.get("FINNHUB_KEY") or "").strip()
    if env:
        return env

    candidates: list[Path] = []
    cwd = Path.cwd()
    for name in _KEY_FILES:
        candidates.append(cwd / name)
    # walk up from this file to find a project root marker
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / "requirements.txt").exists():
            for name in _KEY_FILES:
                candidates.append(parent / name)
            break

    seen: set[Path] = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            continue
        if rp in seen:
            continue
        seen.add(rp)
        try:
            if not rp.is_file():
                continue
            for line in rp.read_text(encoding="utf-8").splitlines():
                line = line.strip().strip('"').strip("'")
                if not line or line.startswith("#"):
                    continue
                # tolerate "FINNHUB_KEY=xxx" formatting too
                if "=" in line and line.upper().startswith("FINNHUB_KEY"):
                    line = line.split("=", 1)[1].strip().strip('"').strip("'")
                if line:
                    return line
        except Exception:
            continue
    return None


def is_enabled() -> bool:
    return _get_api_key() is not None


def _normalize_article(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce a Finnhub article record to the small shape we surface in the UI."""
    title = (raw.get("headline") or raw.get("title") or "").strip()
    if not title:
        return None
    ts = raw.get("datetime") or raw.get("date") or 0
    try:
        ts = int(ts)
    except Exception:
        ts = 0
    iso = ""
    if ts > 0:
        try:
            iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            iso = ""
    return {
        "title": title,
        "url": (raw.get("url") or "").strip(),
        "source": (raw.get("source") or "").strip(),
        "summary": (raw.get("summary") or "").strip()[:400],
        "datetime": iso,
        "ts": ts,
    }


def _http_get(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Call the Finnhub REST API. Returns [] on any failure (network/4xx/5xx)."""
    key = _get_api_key()
    if not key:
        return []
    p = {**params, "token": key}
    try:
        resp = requests.get(
            f"{_FINNHUB_BASE}{path}",
            params=p,
            timeout=_DEFAULT_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "poor-trader-dashboard/0.1"},
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []


def fetch_company_news(
    symbol: str,
    from_date: date,
    to_date: date,
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch /company-news for a US ticker (works for SPY/DIA/QQQ on free tier).
    Cached per (symbol, from..to) range key so repeated dashboard loads are cheap.
    """
    cache_key = f"company:{symbol.upper()}"
    range_key = f"{from_date.isoformat()}..{to_date.isoformat()}"
    if db_path is not None:
        cached = get_cached_news(db_path, cache_key, range_key, max_age_seconds=_NEWS_CACHE_TTL_SECONDS)
        if cached is not None:
            return cached

    raw = _http_get(
        "/company-news",
        {"symbol": symbol.upper(), "from": from_date.isoformat(), "to": to_date.isoformat()},
    )
    out: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        norm = _normalize_article(r)
        if norm:
            out.append(norm)
    out.sort(key=lambda a: a.get("ts", 0), reverse=True)

    if db_path is not None:
        try:
            upsert_cached_news(db_path, cache_key, range_key, out)
        except Exception:
            pass
    return out


def fetch_general_news(
    *,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch /news?category=general (Finnhub returns ~last 24-48h of headlines).
    Cached under the current UTC date so we don't refetch on every refresh.
    """
    today = date.today().isoformat()
    cache_key = "general"
    if db_path is not None:
        cached = get_cached_news(db_path, cache_key, today, max_age_seconds=_NEWS_CACHE_TTL_SECONDS)
        if cached is not None:
            return cached

    raw = _http_get("/news", {"category": "general"})
    out: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        norm = _normalize_article(r)
        if norm:
            out.append(norm)
    out.sort(key=lambda a: a.get("ts", 0), reverse=True)

    if db_path is not None:
        try:
            upsert_cached_news(db_path, cache_key, today, out)
        except Exception:
            pass
    return out


def _filter_by_keywords(
    articles: Iterable[dict[str, Any]],
    keywords: list[str],
) -> list[dict[str, Any]]:
    if not keywords:
        return list(articles)
    kws = [k.lower() for k in keywords if k]
    out: list[dict[str, Any]] = []
    for a in articles:
        hay = f"{a.get('title','')} {a.get('summary','')}".lower()
        if any(k in hay for k in kws):
            out.append(a)
    return out


def _articles_on_date(
    articles: Iterable[dict[str, Any]],
    target: date,
    *,
    window_days: int = 1,
) -> list[dict[str, Any]]:
    """Keep articles whose UTC publication date is within +/- window_days of target."""
    out: list[dict[str, Any]] = []
    for a in articles:
        ts = a.get("ts") or 0
        if not ts:
            continue
        try:
            d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        except Exception:
            continue
        if abs((d - target).days) <= window_days:
            out.append(a)
    return out


def fetch_news_for_index(
    index_meta: dict[str, Any],
    target_day: date,
    *,
    db_path: str | Path | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Get news relevant to a single index on a specific day.

    - US indices (news_proxy = SPY/DIA/QQQ): /company-news for a small window
      around target_day, then filter to that day.
    - Non-US indices: /news?category=general filtered by keyword list.
    """
    proxy = (index_meta.get("news_proxy") or "").strip().upper()
    keywords = list(index_meta.get("kw") or [])

    if proxy:
        # Pull a +/- 2-day window so we still catch news for the most recent
        # trading day even when the call lands on a weekend.
        from_d = target_day - timedelta(days=2)
        to_d = target_day + timedelta(days=1)
        articles = fetch_company_news(proxy, from_d, to_d, db_path=db_path)
        # Prefer same-day, else fall back to the closest-day articles already in window.
        same_day = _articles_on_date(articles, target_day, window_days=0)
        if same_day:
            articles = same_day
        else:
            articles = _articles_on_date(articles, target_day, window_days=2)
        if keywords:
            kw_filtered = _filter_by_keywords(articles, keywords)
            if kw_filtered:
                articles = kw_filtered
        return articles[:limit]

    # Non-US: general feed keyword-filtered.
    general = fetch_general_news(db_path=db_path)
    filtered = _filter_by_keywords(general, keywords)
    same_day = _articles_on_date(filtered, target_day, window_days=1)
    if same_day:
        return same_day[:limit]
    return filtered[:limit]


def fetch_news_for_range(
    index_meta: dict[str, Any],
    days: list[date],
    *,
    db_path: str | Path | None = None,
    per_day_limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """
    Get news for multiple dates in one go (used for significant-move annotation).
    Returns a dict keyed by ISO date string.

    For US indices we make a single /company-news call covering the full range
    then bucket by date. For non-US we reuse the cached general feed.
    """
    if not days:
        return {}

    proxy = (index_meta.get("news_proxy") or "").strip().upper()
    keywords = list(index_meta.get("kw") or [])
    out: dict[str, list[dict[str, Any]]] = {}

    if proxy:
        sorted_days = sorted(days)
        from_d = sorted_days[0] - timedelta(days=2)
        to_d = sorted_days[-1] + timedelta(days=1)
        articles = fetch_company_news(proxy, from_d, to_d, db_path=db_path)
        if keywords:
            kw_filtered = _filter_by_keywords(articles, keywords)
            # Only narrow by keywords if the filter actually keeps something.
            if kw_filtered:
                articles = kw_filtered
        for d in days:
            same_day = _articles_on_date(articles, d, window_days=0)
            if not same_day:
                same_day = _articles_on_date(articles, d, window_days=1)
            out[d.isoformat()] = same_day[:per_day_limit]
        return out

    # Non-US: only the most recent day in the general feed will have useful
    # data, but we still attempt per-day matching by datetime.
    general = fetch_general_news(db_path=db_path)
    filtered = _filter_by_keywords(general, keywords)
    for d in days:
        same_day = _articles_on_date(filtered, d, window_days=1)
        out[d.isoformat()] = same_day[:per_day_limit]
    return out
