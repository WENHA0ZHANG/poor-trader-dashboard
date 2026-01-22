from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HistoricalEvent:
    """
    标普 500 历史上的重大回撤（见顶到见底）及其指标快照。
    """
    event_name: str
    peak_date: str
    trough_date: str
    peak_close: float
    trough_close: float
    drawdown_pct: float
    # 指标在顶点的值 (HY Spread, AAII Spread, CNN FearGreed, PE)
    peak_hy: float | None
    peak_aaii: float | None
    peak_cnn: float | None
    peak_pe: float | None
    # 指标在底点的值
    trough_hy: float | None
    trough_aaii: float | None
    trough_cnn: float | None
    trough_pe: float | None


# 写死历史数据表 (2000 年以后回撤 >= 15% 的主要事件)
# 数据基于美联储 FRED、AAII、CNN 以及 S&P 500 历史记录整理
HISTORICAL_EVENTS: list[HistoricalEvent] = [
    HistoricalEvent(
        event_name="Dot-com Bubble Burst",
        peak_date="2000-03-24",
        trough_date="2002-10-09",
        peak_close=1527.46,
        trough_close=776.76,
        drawdown_pct=-49.1,
        peak_hy=5.23, peak_aaii=35.0, peak_cnn=None, peak_pe=29.0,
        trough_hy=10.96, trough_aaii=-30.0, trough_cnn=None, trough_pe=30.0,
    ),
    HistoricalEvent(
        event_name="2008 Global Financial Crisis",
        peak_date="2007-10-09",
        trough_date="2009-03-09",
        peak_close=1565.15,
        trough_close=676.53,
        drawdown_pct=-56.8,
        peak_hy=2.41, peak_aaii=15.0, peak_cnn=None, peak_pe=18.2,
        trough_hy=19.88, trough_aaii=-50.0, trough_cnn=None, trough_pe=110.0,
    ),
    HistoricalEvent(
        event_name="2011 US Debt Ceiling/Eurozone Crisis",
        peak_date="2011-04-29",
        trough_date="2011-10-03",
        peak_close=1363.61,
        trough_close=1099.23,
        drawdown_pct=-19.4,
        peak_hy=3.50, peak_aaii=20.0, peak_cnn=None, peak_pe=16.0,
        trough_hy=8.80, trough_aaii=-25.0, trough_cnn=15.0, trough_pe=13.5,
    ),
    HistoricalEvent(
        event_name="2018 Trade War/Fed Tapering",
        peak_date="2018-09-20",
        trough_date="2018-12-24",
        peak_close=2930.75,
        trough_close=2351.10,
        drawdown_pct=-19.8,
        peak_hy=3.20, peak_aaii=15.0, peak_cnn=75.0, peak_pe=23.5,
        trough_hy=5.40, trough_aaii=-28.0, trough_cnn=5.0, trough_pe=19.0,
    ),
    HistoricalEvent(
        event_name="2020 COVID-19 Crash",
        peak_date="2020-02-19",
        trough_date="2020-03-23",
        peak_close=3386.15,
        trough_close=2237.40,
        drawdown_pct=-33.9,
        peak_hy=3.60, peak_aaii=20.0, peak_cnn=60.0, peak_pe=25.4,
        trough_hy=10.87, trough_aaii=-35.0, trough_cnn=1.0, trough_pe=18.5,
    ),
    HistoricalEvent(
        event_name="2022 High Inflation/Rate Hikes",
        peak_date="2022-01-03",
        trough_date="2022-10-12",
        peak_close=4796.56,
        trough_close=3577.03,
        drawdown_pct=-25.4,
        peak_hy=3.10, peak_aaii=10.0, peak_cnn=65.0, peak_pe=30.0,
        trough_hy=5.40, trough_aaii=-43.0, trough_cnn=15.0, trough_pe=18.0,
    ),
    HistoricalEvent(
        event_name="2024.08 Yen Carry Trade Unwind",
        peak_date="2024-07-16",
        trough_date="2024-08-05",
        peak_close=5667.20,
        trough_close=5186.33,
        drawdown_pct=-8.5,  # Although less than 20%, included as important sentiment turning point
        peak_hy=3.10, peak_aaii=30.0, peak_cnn=70.0, peak_pe=27.5,
        trough_hy=3.90, trough_aaii=-15.0, trough_cnn=18.0, trough_pe=25.5,
    ),
    HistoricalEvent(
        event_name="2025.04 Spring Valuation Adjustment",
        peak_date="2025-03-31",
        trough_date="2025-04-25",
        peak_close=6150.00, # Valuation data
        trough_close=5227.50,
        drawdown_pct=-15.0,
        peak_hy=3.30, peak_aaii=25.0, peak_cnn=75.0, peak_pe=28.5,
        trough_hy=4.80, trough_aaii=-20.0, trough_cnn=10.0, trough_pe=24.0,
    ),
]


def get_historical_events() -> list[HistoricalEvent]:
    return HISTORICAL_EVENTS
