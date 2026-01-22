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
    o = latest.get(IndicatorId.CNN_PUT_CALL_OPTIONS)
    if o:
        v = float(o.value)
        # Put/Call >= 0.80 biased toward fear/defensive; < 0.6 biased toward greed/arrogance
        bottom = v >= 0.80
        top = v < 0.6
        out.append(
            Signal(
                indicator_id=IndicatorId.CNN_PUT_CALL_OPTIONS,
                top=top,
                bottom=bottom,
                title="Put/Call Ratio (5-Day Average)",
                detail=f"{v:.2f} (<0.60 biased greed/arrogance; >=0.80 biased fear/defensive)",
                meta={"rating": (o.meta or {}).get("rating")},
            )
        )

    # 4) VIX（volatility index）
    o = latest.get(IndicatorId.VIX)
    if o:
        v = float(o.value)
        # VIX > 25 is bottom signal, VIX < 14 is top signal
        top = v < 14
        bottom = v > 25
        out.append(
            Signal(
                indicator_id=IndicatorId.VIX,
                top=top,
                bottom=bottom,
                title="S&P 500 Volatility Index",
                detail=f"{v:.2f} (<14 top; >25 bottom)",
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

    # 6) S&P 500 PE（x）
    o = latest.get(IndicatorId.SP500_PE_RATIO)
    if o:
        v = float(o.value)
        # Both fixed threshold and historical percentile (if available)
        top = v >= 32 or (pe_percentile is not None and pe_percentile >= 0.9)
        bottom = v <= 22 or (pe_percentile is not None and pe_percentile <= 0.1)
        pct_str = f", historical percentile≈{pe_percentile*100:.0f}%" if pe_percentile is not None else ""
        out.append(
            Signal(
                indicator_id=IndicatorId.SP500_PE_RATIO,
                top=top,
                bottom=bottom,
                title="S&P 500 Price-to-Earnings Ratio",
                detail=f"{v:.2f}x (>=32 top valuation; <=22 bottom valuation{pct_str})",
            )
        )

    # 7) Nasdaq 100 PE（x）
    o = latest.get(IndicatorId.NASDAQ100_PE_RATIO)
    if o:
        v = float(o.value)
        top = v > 35
        bottom = v < 28
        out.append(
            Signal(
                indicator_id=IndicatorId.NASDAQ100_PE_RATIO,
                top=top,
                bottom=bottom,
                title="Nasdaq 100 Price-to-Earnings Ratio",
                detail=f"{v:.2f}x (>35 top valuation; <28 bottom valuation)",
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
                title="Nasdaq 100 Stocks Above 20-Day Moving Average (%)",
                detail=f"{v:.2f}% (>80 top; <20 bottom)",
            )
        )

    # 9) HY OAS
    o = latest.get(IndicatorId.US_HIGH_YIELD_SPREAD)
    if o:
        v = float(o.value)
        # Unified conversion to basis points (bp) for threshold judgment
        if o.unit == "percent" or v < 30: # Empirical judgment: if less than 30, usually percentage
            v_bp = v * 100
        else:
            v_bp = v  # Already in bp
        # Unified display as percentage format (e.g., 2.83%)
        val_display = f"{v_bp / 100.0:.2f}%"

        top = v_bp < 280  # Below 2.8%: top risk (extremely optimistic credit)
        bottom = v_bp > 450  # Above 4.5%: bottom signal (panic clearing)
        out.append(
            Signal(
                indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
                top=top,
                bottom=bottom,
                title="US High Yield Option-Adjusted Spread",
                detail=f"Current {val_display} (<2.8% top risk; >4.5% bottom panic)",
            )
        )

    return out


