from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .constants import ALL_INDICATORS, IndicatorId
from .providers import (
    CnnFearGreedProvider,
    FredProvider,
    HttpJsonProvider,
    ManualProvider,
    MultplProvider,
    Nasdaq100PeProvider,
    NdtwProvider,
    Sp500RsiProvider,
    YChartsProvider,
)
from .rules import RULES, RuleContext
from .storage import latest_observation, list_latest, recent_observations, upsert_observations


app = typer.Typer(add_completion=False, help="Six indicators: fetch/ingest/store/bull-bear alerts (CLI)")
console = Console()


def _parse_indicator(v: str) -> IndicatorId:
    try:
        return IndicatorId(v)
    except Exception as e:
        raise typer.BadParameter(f"Unknown indicator: {v} (options: {', '.join(i.value for i in ALL_INDICATORS)})") from e


def _db_path(db: str | None) -> Path:
    return Path(db) if db else Path.cwd() / "trader_alerts.sqlite3"


def _fetch_into_db(dbp: Path, prov: str, config: str | None = None) -> int:
    prov = prov.strip().lower()
    obs = []
    if prov == "fred":
        obs = FredProvider().fetch([IndicatorId.US_HIGH_YIELD_SPREAD])
    elif prov == "cnn":
        obs = CnnFearGreedProvider().fetch([IndicatorId.CNN_FEAR_GREED_INDEX, IndicatorId.CNN_PUT_CALL_OPTIONS])
    elif prov == "vix":
        from .providers.vix import VixProvider
        obs = VixProvider().fetch([IndicatorId.VIX])
    elif prov == "multpl":
        obs = MultplProvider().fetch([IndicatorId.SP500_PE_RATIO])
    elif prov == "nasdaqpe":
        obs = Nasdaq100PeProvider().fetch([IndicatorId.NASDAQ100_PE_RATIO])
    elif prov == "rsi":
        obs = Sp500RsiProvider().fetch([IndicatorId.SP500_RSI])
    elif prov == "ycharts":
        obs = YChartsProvider().fetch([IndicatorId.BOFA_BULL_BEAR])
    elif prov == "ndtw":
        obs = NdtwProvider().fetch([IndicatorId.NASDAQ100_ABOVE_20D_MA])
    elif prov == "http":
        cfg = config or "api_config.yaml"
        obs = HttpJsonProvider(cfg).fetch(list(ALL_INDICATORS))
    else:
        raise typer.BadParameter(f"Unknown provider: {prov} (options: fred/http/multpl/nasdaqpe/cnn/ycharts/rsi/ndtw/all)")

    return upsert_observations(dbp, obs)


def _fetch_all_into_db(dbp: Path, config: str | None = None) -> int:
    total = 0
    # Order: http first (proprietary indicators), then public sentiment/valuation, then fred
    for p in ["http", "ycharts", "cnn", "multpl", "nasdaqpe", "rsi", "fred"]:
        try:
            total += _fetch_into_db(dbp, p, config=config)
        except Exception as e:
            # For example: FRED_API_KEY not configured, http_config missing, etc., just prompt but don't interrupt
            console.print(f"[yellow]Skipping {p}[/yellow]: {e}")
    return total


@app.command()
def init(
    out_dir: str = typer.Option(".", help="Output directory (default current directory)"),
) -> None:
    """
    Generate `manual_input.yaml` template for manual input of proprietary indicators.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    template = """# (Simplified) Current dashboard only keeps "auto-fetchable" indicators.
# For manual input, you can write here, but recommend using `trader fetch ...` directly.

# AAII Bull-Bear Spread (YCharts fetch; example only)
bofa_bull_bear:
  value: 10.94
  unit: "%"
  as_of: "2025-12-18"
  source: "YCharts:AAII"

# US High Yield OAS (TradingEconomics fetch; example only)
us_high_yield_spread:
  value: 283
  unit: "bp"
  as_of: "2025-11-30"
  source: "TradingEconomics"

# S&P 500 PE (Multpl fetch; example only)
sp500_pe_ratio:
  value: 31.28
  unit: "x"
  as_of: "2025-12-28"
  source: "multpl.com"

# CNN Fear & Greed (CNN dataviz fetch; example only)
cnn_fear_greed_index:
  value: 55.51
  unit: "0-100"
  as_of: "2025-12-26"
  source: "CNN:dataviz"
"""

    p = out / "manual_input.yaml"
    if not p.exists():
        p.write_text(template, encoding="utf-8")

    api_template = """# Optional: Integrate your own "real-time API" (generic JSON config)
# You can use any HTTP API (self-built/paid data provider/middle platform), as long as it returns JSON.
#
# Config item description:
# - url: API address
# - method: GET/POST...
# - headers/params: request headers/parameters
# - value_path: path to extract value from JSON (dot-path, like data.value or result.0.value)
# - as_of_path: optional, path to extract date from JSON (ISO, like 2025-03-18)
# - unit/source: only for display and tracing

indicators:
  us_high_yield_spread:
    url: "https://your-api.example.com/hy_oas"
    method: "GET"
    headers:
      Authorization: "Bearer YOUR_TOKEN"
    params: {}
    value_path: "data.value"
    as_of_path: "data.as_of"
    unit: "bp"
    source: "your_api"
"""

    ap = out / "api_config.yaml"
    if not ap.exists():
        ap.write_text(api_template, encoding="utf-8")

    console.print(f"[green]Template generated: [/green]{p}")
    console.print(f"[green]Template generated: [/green]{ap}")
    console.print("Next steps: Edit the file → `trader ingest --file manual_input.yaml` → `trader evaluate`")


@app.command()
def ingest(
    file: str = typer.Option("manual_input.yaml", help="Manual input YAML file path"),
    db: str | None = typer.Option(None, help="SQLite path (default ./trader_alerts.sqlite3)"),
) -> None:
    """
    Write values from `manual_input.yaml` to SQLite.
    """
    dbp = _db_path(db)
    provider = ManualProvider(file)
    obs = provider.fetch(list(ALL_INDICATORS))
    n = upsert_observations(dbp, obs)
    console.print(f"[green]Write completed[/green]: {n} records → {dbp}")


@app.command()
def fetch(
    provider: str = typer.Argument(..., help='Data source: fred/http/multpl/nasdaqpe/cnn/ycharts/rsi/ndtw/all'),
    db: str | None = typer.Option(None, help="SQLite path (default ./trader_alerts.sqlite3)"),
    config: str | None = typer.Option(None, help="Config file when provider=http (default api_config.yaml)"),
) -> None:
    """
    Fetch data from public API and write to SQLite (currently: FRED\'s US High Yield Spread).
    """
    dbp = _db_path(db)
    prov = provider.lower()
    if prov == "fred":
        p = FredProvider()
        obs = p.fetch([IndicatorId.US_HIGH_YIELD_SPREAD])
    elif prov == "http":
        cfg = config or "api_config.yaml"
        p = HttpJsonProvider(cfg)
        obs = p.fetch(list(ALL_INDICATORS))
    elif prov == "multpl":
        p = MultplProvider()
        obs = p.fetch([IndicatorId.SP500_PE_RATIO])
    elif prov == "nasdaqpe":
        p = Nasdaq100PeProvider()
        obs = p.fetch([IndicatorId.NASDAQ100_PE_RATIO])
    elif prov == "cnn":
        p = CnnFearGreedProvider()
        obs = p.fetch([IndicatorId.CNN_FEAR_GREED_INDEX, IndicatorId.CNN_PUT_CALL_OPTIONS])
    elif prov == "ycharts":
        p = YChartsProvider()
        obs = p.fetch([IndicatorId.BOFA_BULL_BEAR])
    elif prov == "rsi":
        p = Sp500RsiProvider()
        obs = p.fetch([IndicatorId.SP500_RSI])
    elif prov == "ndtw":
        p = NdtwProvider()
        obs = p.fetch([IndicatorId.NASDAQ100_ABOVE_20D_MA])
    elif prov == "all":
        n = _fetch_all_into_db(dbp, config=config)
        console.print(f"[green]拉取并写入完成[/green]：{n} 条 → {dbp}")
        return
    else:
        raise typer.BadParameter("provider only supports: fred、http、multpl、nasdaqpe、cnn、ycharts、rsi、ndtw、all")

    n = upsert_observations(dbp, obs)
    console.print(f"[green]Fetch and write completed[/green]: {n} records → {dbp}")


@app.command()
def show(
    db: str | None = typer.Option(None, help="SQLite path (default ./trader_alerts.sqlite3)"),
    refresh: bool = typer.Option(False, help="Fetch latest data before showing (equivalent to running fetch all first)"),
    config: str | None = typer.Option(None, help="HTTP config file when refresh=True (default api_config.yaml)"),
) -> None:
    """
    Show latest values for each indicator.
    """
    dbp = _db_path(db)
    if refresh:
        _fetch_all_into_db(dbp, config=config)
    latest = list_latest(dbp)

    table = Table(title="Latest Indicator Values", show_lines=True)
    table.add_column("Indicator ID", style="cyan")
    table.add_column("Date", style="white")
    table.add_column("Value", style="white")
    table.add_column("Unit", style="white")
    table.add_column("Source", style="magenta")

    for ind in ALL_INDICATORS:
        o = latest.get(ind)
        if not o:
            table.add_row(ind.value, "-", "-", "-", "-")
            continue
        table.add_row(ind.value, o.as_of.isoformat(), str(o.value), o.unit, o.source)

    console.print(table)


@app.command()
def evaluate(
    only: str | None = typer.Option(None, help="Only evaluate specific indicator ID (e.g. us_high_yield_spread)"),
    db: str | None = typer.Option(None, help="SQLite path (default ./trader_alerts.sqlite3)"),
    refresh: bool = typer.Option(False, help="Fetch latest data before evaluation (equivalent to running fetch all first)"),
    config: str | None = typer.Option(None, help="HTTP config file when refresh=True (default api_config.yaml)"),
) -> None:
    """
    Evaluate latest values, output bull/bear alerts (or neutral) for each indicator.
    """
    dbp = _db_path(db)
    if refresh:
        _fetch_all_into_db(dbp, config=config)
    targets = [_parse_indicator(only)] if only else list(ALL_INDICATORS)

    table = Table(title=f"Alert Output ({date.today().isoformat()})", show_lines=True)
    table.add_column("Indicator ID", style="cyan")
    table.add_column("Latest Date", style="white")
    table.add_column("Latest Value", style="white")
    table.add_column("Alert", style="yellow")
    table.add_column("Explanation", style="white")

    for ind in targets:
        latest = latest_observation(dbp, ind)
        h30 = recent_observations(dbp, ind, 35)
        h365 = recent_observations(dbp, ind, 370)
        ctx = RuleContext(latest=latest, history_30d=h30, history_365d=h365)

        rule = RULES.get(ind)
        if not latest:
            table.add_row(ind.value, "-", "-", "No data", "Run ingest or fetch first")
            continue
        if not rule:
            table.add_row(ind.value, latest.as_of.isoformat(), str(latest.value), "Neutral", "No rule yet")
            continue

        alert = rule(ctx)
        table.add_row(
            ind.value,
            latest.as_of.isoformat(),
            f"{latest.value}",
            alert.level.value if alert else "Neutral",
            alert.title if alert else "Not triggered",
        )

    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Listen address"),
    port: int = typer.Option(8501, help="Port"),
    db: str | None = typer.Option(None, help="SQLite path (default ./trader_alerts.sqlite3)"),
    auto_fetch: bool = typer.Option(True, help="Auto-fetch latest data on each page refresh (with cooldown)"),
    providers: str = typer.Option(
        "http,ycharts,cnn,vix,multpl,nasdaqpe,fred,rsi",
        help="Auto-fetch data sources (comma-separated): http,ycharts,cnn,vix,multpl,nasdaqpe,fred,rsi",
    ),
    cooldown: int = typer.Option(3600, help="Auto-fetch cooldown time (seconds), default 1 hour to avoid rate limiting"),
    http_config: str = typer.Option("api_config.yaml", help="Config file path when providers include http"),
) -> None:
    """
    Start web dashboard (FastAPI).

    Web dependencies need to be installed first:
    `pip install -r requirements-web.txt`
    """
    try:
        import uvicorn  # type: ignore
    except Exception:
        console.print("[red]缺少 Web 依赖[/red]：请先执行 `pip install -r requirements-web.txt`")
        raise typer.Exit(code=1)

    from trader_alerts.web.app import create_app

    dbp = _db_path(db)
    app_ = create_app(
        dbp,
        auto_fetch=auto_fetch,
        auto_fetch_providers=[p.strip() for p in providers.split(",") if p.strip()],
        min_interval_seconds=cooldown,
        http_config_path=http_config,
    )
    console.print(f"[green]仪表盘启动[/green]：http://{host}:{port}  （db={dbp}）")
    uvicorn.run(app_, host=host, port=port, log_level="info")


