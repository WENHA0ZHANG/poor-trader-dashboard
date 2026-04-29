from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import IndicatorId
from .models import Observation


@dataclass(frozen=True)
class Signal:
    indicator_id: IndicatorId
    # Top signal: more biased toward "peak/overheating"
    top: bool
    # Bottom signal: more biased toward "trough/panic clearing"
    bottom: bool
    title: str
    detail: str
    meta: dict[str, Any] | None = None


def compute_signals(
    latest: dict[IndicatorId, Observation],
    *,
    pe_percentile: float | None = None,
) -> list[Signal]:
    out: list[Signal] = []

    # 1) Investor Sentiment Bull-Bear Spread（%）
    # Calibration:
    #   - Real "extreme greed" tops were Jan-2018 +33, Nov-2021 +35, Dec-2024 +28.
    #   - Real "extreme fear" bottoms were Mar-2009 -51, Sep-2022 -45,
    #     Apr-2024 -28, Aug-2024 -25.
    #   - ±20 catches early warnings; ±25 marks more selective conviction
    #     readings. We use ±20 here because the table is labelled
    #     "early-warning gauges", not "perfect tops".
    o = latest.get(IndicatorId.BOFA_BULL_BEAR)
    if o:
        v = float(o.value)
        top = v >= 20
        bottom = v <= -20
        out.append(
            Signal(
                indicator_id=IndicatorId.BOFA_BULL_BEAR,
                top=top,
                bottom=bottom,
                title="Investor Sentiment Bull-Bear Spread",
                detail=f"{v:.2f}% (>=+20 top sentiment; <=-20 bottom sentiment)",
            )
        )

    # 2) CNN Fear & Greed（0-100）
    o = latest.get(IndicatorId.CNN_FEAR_GREED_INDEX)
    if o:
        v = float(o.value)
        top = v >= 75
        bottom = v <= 25
        out.append(
            Signal(
                indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
                top=top,
                bottom=bottom,
                title="Fear & Greed Index",
                detail=f"{v:.1f} (>=75 extreme greed; <=25 extreme fear)",
                meta={"rating": (o.meta or {}).get("rating")},
            )
        )

    # 3) CNN Put/Call（5-day avg put/call ratio）
    # CNN's own labels for this 5-day-avg series:
    #   <0.65 = extreme greed, 0.65-0.75 = greed, 0.75-0.85 = fear,
    #   0.85-1.00 = extreme fear, >1.00 = capitulation.
    # Empirical: at major bottoms (Mar-2020, Sep-2022, Aug-2024, Apr-2025)
    # the 5-day P/C printed 1.10-1.35; at frothy tops (early-2024, late-2024)
    # it printed 0.50-0.58.
    # Tightened to require true extremes rather than "fear/greed" levels.
    o = latest.get(IndicatorId.CNN_PUT_CALL_OPTIONS)
    if o:
        v = float(o.value)
        top = v < 0.55      # extreme greed in calls
        bottom = v >= 0.95  # heavy put-buying / panic
        out.append(
            Signal(
                indicator_id=IndicatorId.CNN_PUT_CALL_OPTIONS,
                top=top,
                bottom=bottom,
                title="Put/Call Ratio (5-Day Average)",
                detail=f"{v:.2f} (<0.55 extreme greed; >=0.95 panic put-buying)",
                meta={"rating": (o.meta or {}).get("rating")},
            )
        )

    # 4) VIX（volatility index）
    # Long-run mean ~19.5. Sustained <13 = complacency (late-2017,
    # mid-2024 right before vol-mageddon); spikes >30 = panic (Mar-2020
    # 82, Aug-2024 65, Apr-2025 60). 14/25 catches more events as
    # warnings; >30 is the "real capitulation" line.
    o = latest.get(IndicatorId.VIX)
    if o:
        v = float(o.value)
        top = v < 14
        bottom = v > 25
        out.append(
            Signal(
                indicator_id=IndicatorId.VIX,
                top=top,
                bottom=bottom,
                title="S&P 500 Volatility Index",
                detail=f"{v:.2f} (<14 complacency; >25 fear / >30 panic)",
            )
        )

    # 5) S&P 500 RSI（0-100）
    o = latest.get(IndicatorId.SP500_RSI)
    if o:
        v = float(o.value)
        top = v >= 70
        bottom = v <= 30
        out.append(
            Signal(
                indicator_id=IndicatorId.SP500_RSI,
                top=top,
                bottom=bottom,
                title="S&P 500 Relative Strength Index",
                detail=f"{v:.2f} (>70 overbought; <30 oversold)",
            )
        )

    # 6) S&P 500 PE（x, trailing-twelve-months）
    # Multpl monthly TTM PE history (verified from the actual table):
    #   Real-stock bottoms: Dec-2018 19.39, Oct-2022 20.44, Mar-2020 22.80
    #     (the 2009 print of 110x is an earnings-collapse artefact, not
    #      a "cheap valuation" signal — TTM PE is unreliable around
    #      earnings dislocations).
    #   Real-stock tops: Jan-2018 24, Sep-2018 24, Dec-2020 39.3
    #     (post-COVID earnings dip), Oct-2021 27.3, current ~30.
    # Top ≥ 30 / bottom ≤ 20 captures "true" extremes without firing on
    # every routine pullback.
    o = latest.get(IndicatorId.SP500_PE_RATIO)
    if o:
        v = float(o.value)
        top = v >= 30 or (pe_percentile is not None and pe_percentile >= 0.9)
        bottom = v <= 20 or (pe_percentile is not None and pe_percentile <= 0.1)
        pct_str = f", historical percentile≈{pe_percentile*100:.0f}%" if pe_percentile is not None else ""
        out.append(
            Signal(
                indicator_id=IndicatorId.SP500_PE_RATIO,
                top=top,
                bottom=bottom,
                title="S&P 500 Price-to-Earnings Ratio",
                detail=f"{v:.2f}x (>=30 top valuation; <=20 bottom valuation{pct_str})",
            )
        )

    # 7) Nasdaq 100 PE（x）
    # NDX bottoms typically 19-23x (Oct-2022 ~21, Dec-2018 ~19);
    # tops 32-40x. Previous "bottom 28x" never triggered in real bottoms.
    o = latest.get(IndicatorId.NASDAQ100_PE_RATIO)
    if o:
        v = float(o.value)
        top = v > 35
        bottom = v < 22
        out.append(
            Signal(
                indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                top=top,
                bottom=bottom,
                title="Nasdaq 100 Price-to-Earnings Ratio",
                detail=f"{v:.2f}x (>35 top valuation; <22 bottom valuation)",
            )
        )

    # 8) Nasdaq 100 Stocks Above 20-Day Average（%）
    o = latest.get(IndicatorId.NASDAQ100_ABOVE_20D_MA)
    if o:
        v = float(o.value)
        # Below 20 is bottom, above 80 is top
        top = v > 80
        bottom = v < 20
        out.append(
            Signal(
                indicator_id=IndicatorId.NASDAQ100_ABOVE_20D_MA,
                top=top,
                bottom=bottom,
                title="Nasdaq 100 Above 20-Day Moving Average (%)",
                detail=f"{v:.2f}% (>80 top; <20 bottom)",
            )
        )

    # 9) HY OAS
    # FRED BAMLH0A0HYM2 historical extremes:
    #   Tight (=stock-top warning): 2007-Jun 2.41%, 2014-Jun 3.35%,
    #     2021-Jul 2.85%, 2024-Nov 2.74%, 2025-mid sub-3% range.
    #   Wide (=stock-bottom signal): 2008 22.07%, 2020-Mar 10.87%,
    #     2022-Oct 5.83%, 2024-Aug 3.93%, 2025-Apr 4.95%.
    # 2.8% / 4.5% catches early warnings; >5.5% is "real bottom" zone.
    o = latest.get(IndicatorId.US_HIGH_YIELD_SPREAD)
    if o:
        v = float(o.value)
        if o.unit == "percent" or v < 30:
            v_bp = v * 100
        else:
            v_bp = v
        val_display = f"{v_bp / 100.0:.2f}%"

        top = v_bp < 280
        bottom = v_bp > 450
        out.append(
            Signal(
                indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
                top=top,
                bottom=bottom,
                title="US High Yield Option-Adjusted Spread",
                detail=f"Current {val_display} (<2.8% credit-greed top; >4.5% credit-stress bottom)",
            )
        )

    # 10) CBOE SKEW (tail-risk hedging cost)
    # Historical regimes:
    #   pre-2017: 105-140, with 145+ being a rare extreme
    #   post-2020: 130-170 has become the new normal as institutional
    #              demand for OTM puts is structurally higher
    # Backfilled 1y of ^SKEW shows ~52% of days >=145 in the current
    # regime, so 145 no longer flags an "extreme". Bumped to 155 to
    # capture genuine tail-hedging spikes that historically have led
    # vol events (early-2018, Jan-2020, Sep-2021, Aug-2024).
    o = latest.get(IndicatorId.CBOE_SKEW)
    if o:
        v = float(o.value)
        top = v >= 155
        bottom = False  # SKEW does not produce useful bottom signals
        out.append(
            Signal(
                indicator_id=IndicatorId.CBOE_SKEW,
                top=top,
                bottom=bottom,
                title="CBOE SKEW (Tail-Risk Hedging)",
                detail=f"{v:.1f} (>=155 institutional tail-hedging spike — top warning)",
            )
        )

    # 11) 10Y-2Y Treasury yield curve (T10Y2Y)
    # Inversion <0% has preceded every U.S. recession since 1980.
    # The dangerous window for stocks is when the curve RE-STEEPENS from
    # negative back toward zero (often 6-12 months before bear market).
    # We treat the spread re-entering [0%, 0.6%] band after recent
    # inversion as a top warning. <-0.5% (deep inversion) is itself
    # not directly a bottom signal — bottoms tend to come once the
    # curve has steepened well above 1% and Fed is cutting fast.
    o = latest.get(IndicatorId.YC_10Y_2Y)
    if o:
        v = float(o.value)
        top = -0.05 <= v <= 0.6   # re-steepening danger window
        bottom = v >= 1.5         # late-recession steepening (Fed easing aggressively)
        out.append(
            Signal(
                indicator_id=IndicatorId.YC_10Y_2Y,
                top=top,
                bottom=bottom,
                title="10Y-2Y Treasury Yield Curve",
                detail=(
                    f"{v:+.2f}% (re-steepening from inversion: late-cycle top window; "
                    f">=1.5% Fed-easing-driven bottom window)"
                ),
            )
        )

    return out


