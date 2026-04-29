from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalEvent:
    """
    Major S&P 500 drawdowns since 2000 (peak-to-trough), with snapshots of
    sentiment / valuation / credit indicators.

    Reference values are sourced from public databases and lightly rounded:
      * S&P 500 closes        — S&P / Yahoo Finance historical data
      * High Yield OAS        — FRED series BAMLH0A0HYM2 (ICE BofA US HY)
      * AAII Bull-Bear Spread — AAII Investor Sentiment Survey
                                (https://www.aaii.com/sentimentsurvey)
      * Fear & Greed Index    — CNN Fear & Greed (only available since
                                Oct 2012; older events leave it None)
      * S&P 500 trailing PE   — multpl.com (TTM, GAAP). Note that PE often
                                spikes at recession troughs because the "E"
                                collapses faster than the "P" recovers (so
                                the trough PE can be higher than the peak).
    """

    event_name: str
    peak_date: str
    trough_date: str
    peak_close: float
    trough_close: float
    drawdown_pct: float
    peak_hy: float | None
    peak_aaii: float | None
    peak_cnn: float | None
    peak_pe: float | None
    trough_hy: float | None
    trough_aaii: float | None
    trough_cnn: float | None
    trough_pe: float | None


HISTORICAL_EVENTS: list[HistoricalEvent] = [
    HistoricalEvent(
        event_name="Dot-com Bubble Burst",
        peak_date="2000-03-24",
        trough_date="2002-10-09",
        peak_close=1527.46,
        trough_close=776.76,
        drawdown_pct=-49.1,
        peak_hy=3.78, peak_aaii=25.0, peak_cnn=None, peak_pe=28.0,
        trough_hy=10.97, trough_aaii=-25.0, trough_cnn=None, trough_pe=32.0,
    ),
    HistoricalEvent(
        event_name="2008 Global Financial Crisis",
        peak_date="2007-10-09",
        trough_date="2009-03-09",
        peak_close=1565.15,
        trough_close=676.53,
        drawdown_pct=-56.8,
        peak_hy=3.78, peak_aaii=23.0, peak_cnn=None, peak_pe=22.0,
        trough_hy=19.66, trough_aaii=-51.0, trough_cnn=None, trough_pe=110.0,
    ),
    HistoricalEvent(
        event_name="2011 US Debt Ceiling / Eurozone Crisis",
        peak_date="2011-04-29",
        trough_date="2011-10-03",
        peak_close=1363.61,
        trough_close=1099.23,
        drawdown_pct=-19.4,
        peak_hy=4.39, peak_aaii=12.0, peak_cnn=None, peak_pe=16.0,
        trough_hy=8.87, trough_aaii=-25.0, trough_cnn=None, trough_pe=13.0,
    ),
    HistoricalEvent(
        event_name="2018 Q4 Trade War / Fed Tightening",
        peak_date="2018-09-20",
        trough_date="2018-12-24",
        peak_close=2930.75,
        trough_close=2351.10,
        drawdown_pct=-19.8,
        peak_hy=3.16, peak_aaii=23.0, peak_cnn=80.0, peak_pe=21.0,
        trough_hy=5.34, trough_aaii=-29.0, trough_cnn=3.0, trough_pe=17.5,
    ),
    HistoricalEvent(
        event_name="2020 COVID-19 Crash",
        peak_date="2020-02-19",
        trough_date="2020-03-23",
        peak_close=3386.15,
        trough_close=2237.40,
        drawdown_pct=-33.9,
        peak_hy=3.59, peak_aaii=13.0, peak_cnn=58.0, peak_pe=25.0,
        trough_hy=10.87, trough_aaii=-20.0, trough_cnn=3.0, trough_pe=19.0,
    ),
    HistoricalEvent(
        event_name="2022 Inflation / Rate Hike Bear",
        peak_date="2022-01-03",
        trough_date="2022-10-12",
        peak_close=4796.56,
        trough_close=3577.03,
        drawdown_pct=-25.4,
        peak_hy=3.05, peak_aaii=-6.0, peak_cnn=52.0, peak_pe=28.0,
        trough_hy=5.23, trough_aaii=-35.0, trough_cnn=17.0, trough_pe=19.0,
    ),
    HistoricalEvent(
        event_name="2024.08 Yen Carry Trade Unwind",
        peak_date="2024-07-16",
        trough_date="2024-08-05",
        peak_close=5667.20,
        trough_close=5186.33,
        drawdown_pct=-8.5,  # included as a sentiment-only turning point
        peak_hy=3.05, peak_aaii=30.0, peak_cnn=56.0, peak_pe=28.5,
        trough_hy=3.81, trough_aaii=-5.0, trough_cnn=25.0, trough_pe=26.0,
    ),
    HistoricalEvent(
        event_name="2025.04 Tariff Shock",
        peak_date="2025-02-19",
        trough_date="2025-04-08",
        peak_close=6144.15,
        trough_close=4982.77,
        drawdown_pct=-18.9,
        peak_hy=2.84, peak_aaii=-12.0, peak_cnn=50.0, peak_pe=30.0,
        trough_hy=4.61, trough_aaii=-38.0, trough_cnn=4.0, trough_pe=23.0,
    ),
]


def get_historical_events() -> list[HistoricalEvent]:
    return HISTORICAL_EVENTS
