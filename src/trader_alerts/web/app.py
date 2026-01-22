from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from ..constants import ALL_INDICATORS
from ..providers import (
    CnnFearGreedProvider,
    FredProvider,
    HttpJsonProvider,
    ManualProvider,
    MultplProvider,
    Nasdaq100PeProvider,
    NdtwProvider,
    Sp500RsiProvider,
    TradingEconomicsProvider,
    VixProvider,
    YChartsProvider,
)
from ..constants import IndicatorId
from ..signals import compute_signals
from ..service import compute_alerts
from ..storage import list_latest, upsert_observations, get_last_update_time
from ..market import get_us_index_overview_rows


def create_app(
    db_path: str | Path | None = None,
    *,
    auto_fetch: bool = True,  # Auto-fetch enabled by default
    auto_fetch_providers: list[str] | None = None,
    min_interval_seconds: int = 3600,  # Auto-fetch every 1 hour
    http_config_path: str | Path = "api_config.yaml",
) -> FastAPI:
    app = FastAPI(title="Trader Dashboard", version="0.1.0")

    root = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(root / "templates"))

    resolved_db = Path(db_path) if db_path else (Path.cwd() / "trader_alerts.sqlite3")
    # Simple cache: avoid fetching long historical web pages on every refresh
    cached_pe_monthly: dict | None = None
    cached_market_rows: list[dict[str, Any]] = []
    cached_market_at: datetime | None = None
    market_lock = threading.Lock()
    market_refreshing = False

    # Default: fetch all dashboard indicators (can be overridden by auto_fetch_providers)
    providers = [
        p.strip().lower()
        for p in (
            auto_fetch_providers
            or ["http", "ycharts", "cnn", "vix", "multpl", "nasdaqpe", "fred", "rsi", "ndtw"]
        )
        if p.strip()
    ]
    cooldown = max(0, int(min_interval_seconds))
    last_fetch_at: dict[str, datetime] = {}
    http_cfg = Path(http_config_path)

    def _should_fetch(name: str, now: datetime) -> bool:
        last = last_fetch_at.get(name)
        if not last:
            return True
        return (now - last) >= timedelta(seconds=cooldown)

    def _auto_fetch_now(requested: bool) -> tuple[list[str], list[str]]:
        """
        返回 (ok_messages, error_messages)
        """
        if not (auto_fetch or requested):
            return ([], [])

        now = datetime.now(timezone.utc)
        ok: list[str] = []
        err: list[str] = []

        for name in providers:
            # 如果用户显式 refresh=1，视为“强制刷新”，不受 cooldown 影响
            if (not requested) and (not _should_fetch(name, now)):
                continue
            try:
                if name == "cnn":
                    obs = CnnFearGreedProvider().fetch([IndicatorId.CNN_FEAR_GREED_INDEX, IndicatorId.CNN_PUT_CALL_OPTIONS])
                elif name == "vix":
                    obs = VixProvider().fetch([IndicatorId.VIX])
                elif name == "multpl":
                    obs = MultplProvider().fetch([])
                elif name == "nasdaqpe":
                    obs = Nasdaq100PeProvider().fetch([IndicatorId.NASDAQ100_PE_RATIO])
                elif name == "rsi":
                    obs = Sp500RsiProvider().fetch([IndicatorId.SP500_RSI])
                elif name == "fred":
                    obs = FredProvider().fetch([IndicatorId.US_HIGH_YIELD_SPREAD])
                elif name == "http":
                    if not http_cfg.exists():
                        raise RuntimeError(f"Missing http config file: {http_cfg} (please run `trader init` first or create manually)")
                    obs = HttpJsonProvider(http_cfg).fetch(list(ALL_INDICATORS))
                elif name == "ycharts":
                    obs = YChartsProvider().fetch([IndicatorId.BOFA_BULL_BEAR])
                elif name == "ndtw":
                    obs = NdtwProvider().fetch([IndicatorId.NASDAQ100_ABOVE_20D_MA])
                else:
                    err.append(f"Unknown provider: {name}")
                    continue

                if obs:
                    upsert_observations(resolved_db, obs)
                    ok.append(f"{name}: wrote {len(obs)} records")
                else:
                    ok.append(f"{name}: no data")
                last_fetch_at[name] = now
            except Exception as e:
                err.append(f"{name}: {e}")

        return (ok, err)

    def _kick_market_refresh(*, force: bool) -> None:
        """
        异步刷新 market cache：不要阻塞首页渲染。
        """
        nonlocal cached_market_rows, cached_market_at, market_refreshing

        with market_lock:
            if market_refreshing:
                return
            now = datetime.now(timezone.utc)
            if (not force) and cached_market_at and (now - cached_market_at) <= timedelta(seconds=60):
                return
            market_refreshing = True

        def _run() -> None:
            nonlocal cached_market_rows, cached_market_at, market_refreshing
            try:
                rows = get_us_index_overview_rows()
                with market_lock:
                    cached_market_rows = rows or []
                    cached_market_at = datetime.now(timezone.utc)
            except Exception:
                # 保留旧数据（或空），避免失败影响页面
                pass
            finally:
                with market_lock:
                    market_refreshing = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> Any:
        refresh = str(request.query_params.get("refresh") or "").strip().lower() in {"1", "true", "yes", "y"}
        ok_msgs, err_msgs = _auto_fetch_now(refresh)
        latest = list_latest(resolved_db)
        alerts = compute_alerts(resolved_db, list(ALL_INDICATORS))

        # Calculate last update time
        last_update_time = get_last_update_time(resolved_db)
        if last_update_time:
            # 转换为本地时区显示（假设用户在东八区）
            last_update_time = last_update_time.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_update_time = None

        # US market overview：改成异步刷新（不阻塞页面）
        _kick_market_refresh(force=refresh)
        with market_lock:
            market_rows = list(cached_market_rows)

        # History (hardcoded in historical.py, no longer dynamically fetch long historical data)
        from ..historical import get_historical_events
        bear_rows = [asdict(e) for e in get_historical_events()]

        # Only fetch monthly PE table once when calculating PE percentile (optional, default off to keep fast loading)
        pe_pct = None
        want_history = str(request.query_params.get("history") or "").strip().lower() in {"1", "true", "yes", "y"}
        if want_history:
            try:
                if cached_pe_monthly is None:
                    from ..historical import fetch_multpl_pe_monthly
                    cached_pe_monthly = fetch_multpl_pe_monthly()

                pe_latest = latest.get(IndicatorId.SP500_PE_RATIO)
                if pe_latest and cached_pe_monthly:
                    vals = sorted(cached_pe_monthly.values())
                    v = float(pe_latest.value)
                    import bisect
                    pe_pct = bisect.bisect_right(vals, v) / max(1, len(vals))
            except Exception:
                pass # Ignore PE percentile calculation errors to ensure page display

        signals = compute_signals(latest, pe_percentile=pe_pct)
        top_signals = [s for s in signals if s.top]
        bottom_signals = [s for s in signals if s.bottom]

        # Build signal dictionary for easy lookup
        signal_map = {s.indicator_id: s for s in signals}

        # Indicator ID to display name mapping (use default name if no signal)
        indicator_names = {
            IndicatorId.US_HIGH_YIELD_SPREAD: "US High Yield Option-Adjusted Spread",
            IndicatorId.BOFA_BULL_BEAR: "Investor Sentiment Bull-Bear Spread",
            IndicatorId.CNN_FEAR_GREED_INDEX: "Fear & Greed Index",
            IndicatorId.CNN_PUT_CALL_OPTIONS: "Put/Call Ratio (5-Day Average)",
            IndicatorId.SP500_PE_RATIO: "S&P 500 Price-to-Earnings Ratio",
            IndicatorId.NASDAQ100_PE_RATIO: "Nasdaq 100 Price-to-Earnings Ratio",
            IndicatorId.SP500_RSI: "S&P 500 Relative Strength Index",
            IndicatorId.NASDAQ100_ABOVE_20D_MA: "Nasdaq 100 Stocks Above 20-Day Moving Average (%)",
            IndicatorId.VIX: "S&P 500 Volatility Index",
        }

        # Indicator ID to source URL mapping
        indicator_source_urls = {
            IndicatorId.US_HIGH_YIELD_SPREAD: "https://tradingeconomics.com/united-states/bofa-merrill-lynch-us-high-yield-option-adjusted-spread-fed-data.html",
            IndicatorId.BOFA_BULL_BEAR: "https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread",
            IndicatorId.CNN_FEAR_GREED_INDEX: "https://edition.cnn.com/markets/fear-and-greed",
            IndicatorId.CNN_PUT_CALL_OPTIONS: "https://edition.cnn.com/markets/fear-and-greed",
            IndicatorId.SP500_PE_RATIO: "https://www.multpl.com/s-p-500-pe-ratio",
            IndicatorId.NASDAQ100_PE_RATIO: "https://www.barrons.com/market-data/stocks/us/pe-yields",
            IndicatorId.SP500_RSI: "https://www.investing.com/indices/us-spx-500-technical",
            IndicatorId.NASDAQ100_ABOVE_20D_MA: "https://www.barchart.com/stocks/quotes/$NDTW",
            IndicatorId.VIX: "https://edition.cnn.com/markets/fear-and-greed",
        }

        # Make it easier to use in template
        latest_rows = []
        for ind in ALL_INDICATORS:
            o = latest.get(ind)
            s = signal_map.get(ind)
            # Use signal title first, otherwise use default name
            name = s.title if s else indicator_names.get(ind, ind.value)

            # Format values: special handling for US High Yield Spread (convert from bp to % display)
            value_display = o.value if o else None
            if value_display is not None:
                try:
                    if ind == IndicatorId.US_HIGH_YIELD_SPREAD:
                        # US High Yield Spread stored in bp, display as percentage (without % symbol, % shown in unit column)
                        value_display = f"{float(value_display) / 100.0:.2f}"
                    elif ind == IndicatorId.SP500_RSI:
                        value_display = f"{float(value_display):.2f}"
                    elif ind in {IndicatorId.CNN_FEAR_GREED_INDEX, IndicatorId.CNN_PUT_CALL_OPTIONS, IndicatorId.NASDAQ100_ABOVE_20D_MA}:
                        value_display = f"{float(value_display):.2f}"
                    elif ind in {IndicatorId.SP500_PE_RATIO, IndicatorId.NASDAQ100_PE_RATIO}:
                        value_display = f"{float(value_display):.2f}"
                except (ValueError, TypeError):
                    pass

            # Special handling: unit display optimization
            unit_display = o.unit if o else None
            if ind == IndicatorId.US_HIGH_YIELD_SPREAD and unit_display == "bp":
                unit_display = "%"
            elif unit_display == "percent":
                unit_display = "%"
            
            latest_rows.append(
                {
                    "id": ind.value,
                    "name": name,
                    "as_of": o.as_of.strftime("%m-%d") if o else None,
                    "value": value_display,
                    "unit": unit_display,
                    "source": o.source if o else None,
                    "source_url": indicator_source_urls.get(ind),
                    "is_top": s.top if s else False,
                    "is_bottom": s.bottom if s else False,
                }
            )

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "db_path": str(resolved_db),
                "latest_rows": latest_rows,
                "last_update_time": last_update_time,
                "market_rows": market_rows,
                "alerts": [asdict(a) for a in alerts],
                "auto_fetch": auto_fetch,
                "auto_fetch_enabled": getattr(app.state, 'auto_fetch_enabled', auto_fetch),
                "auto_fetch_providers": providers,
                "cooldown_seconds": cooldown,
                "fetch_ok": ok_msgs,
                "fetch_err": err_msgs,
                "bear_rows": bear_rows,
                "signals": signals,
                "top_signals": top_signals,
                "bottom_signals": bottom_signals,
                "top_score": len(top_signals),
                "bottom_score": len(bottom_signals),
                "pe_percentile": pe_pct,
                "sources": [
                    {"name": "US High Yield OAS (Primary)", "url": "https://tradingeconomics.com/united-states/bofa-merrill-lynch-us-high-yield-option-adjusted-spread-fed-data.html"},
                    {"name": "AAII Bull-Bear Spread", "url": "https://ycharts.com/indicators/us_investor_sentiment_bull_bear_spread"},
                    {"name": "CNN Fear & Greed", "url": "https://edition.cnn.com/markets/fear-and-greed"},
                    {"name": "CNN Put/Call (Same source as Fear&Greed)", "url": "https://edition.cnn.com/markets/fear-and-greed"},
                    {"name": "S&P 500 PE Ratio", "url": "https://www.multpl.com/s-p-500-pe-ratio"},
                    {"name": "Nasdaq 100 PE Ratio", "url": "https://www.barrons.com/market-data/stocks/us/pe-yields"},
                    {"name": "S&P 500 RSI", "url": "https://www.investing.com/indices/us-spx-500-technical"},
                    {"name": "Nasdaq 100 Above 20D MA (Primary)", "url": "https://eoddata.com/stockquote/INDEX/NDTW.htm"},
                    {"name": "Nasdaq 100 Above 20D MA (Alternative)", "url": "https://www.barchart.com/stocks/quotes/$NDTW"},
                    {"name": "Nasdaq 100 Above 20D MA (Alternative)", "url": "https://www.tradingview.com/symbols/INDEX-NDTW/"},
                    {"name": "VIX (CNN Fear & Greed component)", "url": "https://edition.cnn.com/markets/fear-and-greed"},
                    {"name": "US Stock Indices (S&P/Dow/Nasdaq) Daily CSV", "url": "https://stooq.com/q/d/l/"},
                ],
            },
        )

    @app.get("/api/market-overview")
    def api_market_overview(request: Request) -> dict[str, Any]:
        force = str(request.query_params.get("refresh") or "").strip().lower() in {"1", "true", "yes", "y"}
        _kick_market_refresh(force=force)
        with market_lock:
            rows = list(cached_market_rows)
            at = cached_market_at
            refreshing = market_refreshing
        return {
            "rows": rows,
            "as_of_utc": at.isoformat() if at else None,
            "refreshing": refreshing,
        }

    @app.get("/api/latest")
    def api_latest() -> Any:
        latest = list_latest(resolved_db)
        out = {}
        for ind, o in latest.items():
            out[ind.value] = {
                "as_of": o.as_of.isoformat(),
                "value": o.value,
                "unit": o.unit,
                "source": o.source,
                "meta": o.meta or {},
            }
        return out

    @app.get("/api/alerts")
    def api_alerts() -> Any:
        alerts = compute_alerts(resolved_db, list(ALL_INDICATORS))
        return [asdict(a) for a in alerts]

    # Store auto_fetch state for toggling (simplified approach)
    app.state.auto_fetch_enabled = auto_fetch

    @app.post("/api/toggle-autofetch")
    def toggle_autofetch() -> dict[str, Any]:
        try:
            # Toggle the state
            app.state.auto_fetch_enabled = not app.state.auto_fetch_enabled
            return {
                "success": True,
                "auto_fetch": app.state.auto_fetch_enabled,
                "message": f"Auto-fetch {'enabled' if app.state.auto_fetch_enabled else 'disabled'}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }

    return app


# Create default app instance for uvicorn
app = create_app()


