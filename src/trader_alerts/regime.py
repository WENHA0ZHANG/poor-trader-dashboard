"""
Market Regime composite — turn the dashboard's individual indicators
into a single "should I buy / should I be cautious" reading.

Design philosophy
-----------------
Each individual indicator on this dashboard is an "early-warning gauge",
not a trading order. Real traders look at them collectively, weighing
the high-quality signals more heavily than the noisy ones. This module
formalises that intuition into a reproducible score.

Two-axis scoring
----------------
For every indicator we have a value for, we award:

  - a TIER (1, 2 or 3) — how extreme the reading is (1 = mild,
    3 = full panic / euphoria), and
  - a SIGN — positive for "argues for buying" (oversold / panic /
    cheap-valuation / elevated-credit-stress), negative for "argues
    for caution" (overbought / euphoric / expensive / complacent).

The signed tier is then multiplied by the indicator's WEIGHT — a
quality multiplier that reflects how leading / clean the indicator
historically is. Heavy hitters (VIX, HY OAS, valuation, breadth) have
weight ≥ 1.0; noisier or indirect signals (AAII Bull-Bear, SKEW, NDX
trailing PE) have weight < 1.0.

The total `score` (sum of weighted contributions) is mapped to one of
seven bands (Strong Buy → Strong Risk).

Both the score AND every indicator's individual contribution are
exposed so the dashboard can show *why* the regime label was chosen.
No black box.

Calibration of the tier thresholds and weights was done by inspecting
the historical extremes that actually preceded major drawdowns vs.
major rallies after 2000 (FRED, multpl, CNN dataviz, Yahoo VIX/SKEW,
AAII Bull-Bear). The tier thresholds match `signals.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import IndicatorId, ALL_INDICATORS
from .models import Observation


# ---------- per-indicator weights ----------------------------------------
#
# Quality multipliers. Higher weight = the indicator is historically
# more leading / less noisy / harder to game. These were chosen by
# qualitative review, not back-test, so they are deliberately discrete.
#
# Heuristics behind the numbers:
#
#   1.5  VIX           Real-time options-implied volatility — fast,
#                      hard to manipulate, decades of clean history.
#   1.5  HY OAS        Credit-stress is the cleanest "macro is breaking"
#                      indicator and historically leads equity bottoms.
#   1.2  S&P PE        Valuation matters but is slow-moving and noisy
#                      around earnings dislocations (e.g. 2009 spike).
#   1.0  F&G           CNN composite — already an aggregate.
#   1.0  Put/Call      Cleaner sentiment than survey data.
#   1.0  NDX > 20d MA  Breadth — "real money" oriented.
#   1.0  10Y-2Y curve  Slow but extremely reliable late-cycle signal.
#   0.7  AAII B-B      Self-reported survey, weekly, very noisy.
#   0.7  RSI           Pure price momentum — easily mean-reverting,
#                      doesn't add much beyond VIX/breadth.
#   0.7  NDX PE        Less standard, sparser history.
#   0.6  CBOE SKEW     Top-only, indirect, structurally elevated since
#                      2020 so the threshold is a moving target.
#
INDICATOR_WEIGHT: dict[IndicatorId, float] = {
    IndicatorId.VIX:                   1.5,
    IndicatorId.US_HIGH_YIELD_SPREAD:  1.5,
    IndicatorId.SP500_PE_RATIO:        1.2,
    IndicatorId.CNN_FEAR_GREED_INDEX:  1.0,
    IndicatorId.CNN_PUT_CALL_OPTIONS:  1.0,
    IndicatorId.NASDAQ100_ABOVE_20D_MA: 1.0,
    IndicatorId.YC_10Y_2Y:             1.0,
    IndicatorId.BOFA_BULL_BEAR:        0.7,
    IndicatorId.SP500_RSI:             0.7,
    IndicatorId.NASDAQ100_PE_RATIO:    0.7,
    IndicatorId.CBOE_SKEW:             0.6,
}


# ---------- per-indicator contribution ------------------------------------

@dataclass(frozen=True)
class _IndicatorContribution:
    indicator_id: IndicatorId
    title: str
    value: float
    unit: str
    tier: int             # signed: +N = bottom/buy; -N = top/risk; 0 = neutral
    weight: float
    points: float         # tier * weight (the actual score contribution)
    reason: str           # short explanation


def _score_one(o: Observation, *, recently_inverted: bool) -> _IndicatorContribution | None:
    """
    Return one indicator's tier + weighted score contribution.

    `recently_inverted` indicates whether the 10Y-2Y curve was below 0
    at any point in the last ~24 months. The yield-curve top signal
    only fires after a real prior inversion — being at +0.4% for years
    without a prior inversion is normal mid-cycle and shouldn't flag a
    top by itself.
    """
    ind = o.indicator_id
    v = float(o.value)
    w = INDICATOR_WEIGHT.get(ind, 1.0)

    # ---- VIX --------------------------------------------------------------
    if ind == IndicatorId.VIX:
        if v >= 40:   return _c(ind, "VIX", v, "", +3, w, f"VIX {v:.1f} ≥40 panic capitulation")
        if v >= 30:   return _c(ind, "VIX", v, "", +2, w, f"VIX {v:.1f} >30 fear")
        if v >  25:   return _c(ind, "VIX", v, "", +1, w, f"VIX {v:.1f} >25 elevated fear")
        if v <  12:   return _c(ind, "VIX", v, "", -2, w, f"VIX {v:.1f} <12 extreme complacency")
        if v <  14:   return _c(ind, "VIX", v, "", -1, w, f"VIX {v:.1f} <14 complacency")
        return _c(ind, "VIX", v, "", 0, w, "VIX in normal range")

    # ---- CNN Fear & Greed ------------------------------------------------
    if ind == IndicatorId.CNN_FEAR_GREED_INDEX:
        if v <= 10:   return _c(ind, "Fear & Greed", v, "", +3, w, f"F&G {v:.0f} ≤10 capitulation")
        if v <= 20:   return _c(ind, "Fear & Greed", v, "", +2, w, f"F&G {v:.0f} ≤20 extreme fear")
        if v <= 25:   return _c(ind, "Fear & Greed", v, "", +1, w, f"F&G {v:.0f} ≤25 fear")
        if v >= 85:   return _c(ind, "Fear & Greed", v, "", -2, w, f"F&G {v:.0f} ≥85 extreme greed")
        if v >= 75:   return _c(ind, "Fear & Greed", v, "", -1, w, f"F&G {v:.0f} ≥75 greed")
        return _c(ind, "Fear & Greed", v, "", 0, w, "F&G in normal range")

    # ---- CNN Put/Call (5-day average) ------------------------------------
    if ind == IndicatorId.CNN_PUT_CALL_OPTIONS:
        if v >= 1.20: return _c(ind, "Put/Call (5d)", v, "", +3, w, f"P/C {v:.2f} ≥1.20 panic put-buying")
        if v >= 1.05: return _c(ind, "Put/Call (5d)", v, "", +2, w, f"P/C {v:.2f} ≥1.05 heavy put-buying")
        if v >= 0.95: return _c(ind, "Put/Call (5d)", v, "", +1, w, f"P/C {v:.2f} ≥0.95 elevated fear")
        if v <  0.50: return _c(ind, "Put/Call (5d)", v, "", -2, w, f"P/C {v:.2f} <0.50 extreme call greed")
        if v <  0.55: return _c(ind, "Put/Call (5d)", v, "", -1, w, f"P/C {v:.2f} <0.55 call greed")
        return _c(ind, "Put/Call (5d)", v, "", 0, w, "P/C in normal range")

    # ---- AAII Bull-Bear Spread (filed under BOFA_BULL_BEAR) --------------
    if ind == IndicatorId.BOFA_BULL_BEAR:
        if v <= -30:  return _c(ind, "AAII Bull-Bear", v, "%", +2, w, f"{v:.1f}% ≤-30 deep bearish sentiment")
        if v <= -20:  return _c(ind, "AAII Bull-Bear", v, "%", +1, w, f"{v:.1f}% ≤-20 bearish sentiment")
        if v >=  30:  return _c(ind, "AAII Bull-Bear", v, "%", -2, w, f"{v:.1f}% ≥+30 deep bullish sentiment")
        if v >=  20:  return _c(ind, "AAII Bull-Bear", v, "%", -1, w, f"{v:.1f}% ≥+20 bullish sentiment")
        return _c(ind, "AAII Bull-Bear", v, "%", 0, w, "Sentiment in normal range")

    # ---- S&P 500 RSI(14) -------------------------------------------------
    if ind == IndicatorId.SP500_RSI:
        if v <  25:   return _c(ind, "S&P 500 RSI", v, "", +2, w, f"RSI {v:.1f} <25 deeply oversold")
        if v <  30:   return _c(ind, "S&P 500 RSI", v, "", +1, w, f"RSI {v:.1f} <30 oversold")
        if v >  80:   return _c(ind, "S&P 500 RSI", v, "", -2, w, f"RSI {v:.1f} >80 deeply overbought")
        if v >  70:   return _c(ind, "S&P 500 RSI", v, "", -1, w, f"RSI {v:.1f} >70 overbought")
        return _c(ind, "S&P 500 RSI", v, "", 0, w, "RSI in normal range")

    # ---- HY OAS (stored in bp) -------------------------------------------
    if ind == IndicatorId.US_HIGH_YIELD_SPREAD:
        bp = v if (o.unit == "bp" or v > 30) else v * 100
        pct = bp / 100.0
        if bp >= 700: return _c(ind, "HY OAS", pct, "%", +3, w, f"HY {pct:.2f}% ≥7% credit panic")
        if bp >= 550: return _c(ind, "HY OAS", pct, "%", +2, w, f"HY {pct:.2f}% ≥5.5% credit stress")
        if bp >= 450: return _c(ind, "HY OAS", pct, "%", +1, w, f"HY {pct:.2f}% ≥4.5% credit stress")
        if bp <= 250: return _c(ind, "HY OAS", pct, "%", -2, w, f"HY {pct:.2f}% ≤2.5% credit complacency")
        if bp <= 280: return _c(ind, "HY OAS", pct, "%", -1, w, f"HY {pct:.2f}% ≤2.8% credit-greed")
        return _c(ind, "HY OAS", pct, "%", 0, w, "HY OAS in normal range")

    # ---- Nasdaq 100 % Above 20-Day MA ------------------------------------
    if ind == IndicatorId.NASDAQ100_ABOVE_20D_MA:
        if v <  10:   return _c(ind, "NDX > 20d MA", v, "%", +2, w, f"{v:.0f}% <10 broad capitulation")
        if v <  20:   return _c(ind, "NDX > 20d MA", v, "%", +1, w, f"{v:.0f}% <20 broad selloff")
        if v >  90:   return _c(ind, "NDX > 20d MA", v, "%", -2, w, f"{v:.0f}% >90 extreme breadth thrust")
        if v >  80:   return _c(ind, "NDX > 20d MA", v, "%", -1, w, f"{v:.0f}% >80 stretched breadth")
        return _c(ind, "NDX > 20d MA", v, "%", 0, w, "Breadth in normal range")

    # ---- S&P 500 trailing PE ---------------------------------------------
    if ind == IndicatorId.SP500_PE_RATIO:
        if v <= 18:   return _c(ind, "S&P 500 PE", v, "x", +2, w, f"PE {v:.1f}x ≤18 deep value")
        if v <= 20:   return _c(ind, "S&P 500 PE", v, "x", +1, w, f"PE {v:.1f}x ≤20 cheap valuation")
        if v >= 33:   return _c(ind, "S&P 500 PE", v, "x", -2, w, f"PE {v:.1f}x ≥33 extreme valuation")
        if v >= 30:   return _c(ind, "S&P 500 PE", v, "x", -1, w, f"PE {v:.1f}x ≥30 expensive")
        return _c(ind, "S&P 500 PE", v, "x", 0, w, "PE in normal range")

    # ---- Nasdaq 100 trailing PE ------------------------------------------
    if ind == IndicatorId.NASDAQ100_PE_RATIO:
        if v <  22:   return _c(ind, "NDX 100 PE", v, "x", +1, w, f"NDX PE {v:.1f}x <22 cheap")
        if v >  35:   return _c(ind, "NDX 100 PE", v, "x", -1, w, f"NDX PE {v:.1f}x >35 expensive")
        return _c(ind, "NDX 100 PE", v, "x", 0, w, "NDX PE in normal range")

    # ---- CBOE SKEW (top-only) --------------------------------------------
    if ind == IndicatorId.CBOE_SKEW:
        if v >= 160:  return _c(ind, "CBOE SKEW", v, "", -2, w, f"SKEW {v:.1f} ≥160 extreme tail-hedging")
        if v >= 155:  return _c(ind, "CBOE SKEW", v, "", -1, w, f"SKEW {v:.1f} ≥155 tail-hedging spike")
        return _c(ind, "CBOE SKEW", v, "", 0, w, "SKEW in normal range")

    # ---- 10Y-2Y yield curve (re-steepening top window) -------------------
    if ind == IndicatorId.YC_10Y_2Y:
        if recently_inverted and -0.05 <= v <= 0.6:
            return _c(ind, "10Y-2Y Curve", v, "%", -1, w,
                      f"{v:+.2f}% in re-steepening top window after recent inversion")
        if v >= 1.5:
            return _c(ind, "10Y-2Y Curve", v, "%", 0, w,
                      f"{v:+.2f}% steep curve (Fed-easing late stage)")
        return _c(ind, "10Y-2Y Curve", v, "%", 0, w, "Curve in normal range")

    return None


def _c(ind: IndicatorId, title: str, value: float, unit: str,
       tier: int, weight: float, reason: str) -> _IndicatorContribution:
    return _IndicatorContribution(
        indicator_id=ind, title=title, value=value, unit=unit,
        tier=tier, weight=weight,
        points=round(tier * weight, 2),
        reason=reason,
    )


# ---------- aggregation ---------------------------------------------------

# Banding: (min_score_inclusive, label, css_class)
# Score is a weighted sum so it's a float, not int.
_BANDS: list[tuple[float, str, str]] = [
    (  9.0,  "Strong Buy",   "regime-strong-buy"),
    (  4.5,  "Buy",          "regime-buy"),
    (  1.5,  "Cautious Buy", "regime-cautious-buy"),
    ( -1.5,  "Neutral",      "regime-neutral"),
    ( -4.5,  "Caution",      "regime-caution"),
    ( -9.0,  "Risk",         "regime-risk"),
    (-1e9,   "Strong Risk",  "regime-strong-risk"),
]


@dataclass
class MarketRegime:
    score: float           # weighted sum, can be a fractional number
    buy_points: float      # sum of all positive contributions
    risk_points: float     # absolute sum of all negative contributions
    label: str             # English label only
    css_class: str
    summary: str
    contributions: list[dict] = field(default_factory=list)
    coverage: int = 0      # how many indicators contributed (had data)
    total: int = 0         # how many indicators were considered


def _classify(score: float) -> tuple[str, str]:
    for threshold, label, css in _BANDS:
        if score >= threshold:
            return label, css
    return _BANDS[-1][1], _BANDS[-1][2]


def compute_market_regime(
    latest: dict[IndicatorId, Observation],
    *,
    yc_recently_inverted: bool = True,
) -> MarketRegime:
    """
    Build a composite regime label from the dashboard's latest readings.

    `yc_recently_inverted` should reflect whether the 10Y-2Y has been
    below zero at any point in the past ~24 months. The caller is free
    to override based on the actual stored history.
    """
    contributions: list[_IndicatorContribution] = []
    considered = 0
    for ind in latest:
        considered += 1
        c = _score_one(latest[ind], recently_inverted=yc_recently_inverted)
        if c is not None:
            contributions.append(c)

    buy = round(sum(c.points for c in contributions if c.points > 0), 2)
    risk = round(-sum(c.points for c in contributions if c.points < 0), 2)
    score = round(buy - risk, 2)
    label, css = _classify(score)

    fired = [c for c in contributions if c.tier != 0]
    fired.sort(key=lambda c: -abs(c.points))
    if not fired:
        summary = "All indicators in normal ranges."
    else:
        positives = [c for c in fired if c.points > 0]
        negatives = [c for c in fired if c.points < 0]
        parts = []
        if positives:
            parts.append("Bottom signals: " +
                         ", ".join(f"{c.title} ({c.points:+.1f})" for c in positives))
        if negatives:
            parts.append("Top signals: " +
                         ", ".join(f"{c.title} ({c.points:+.1f})" for c in negatives))
        summary = " · ".join(parts)

    # Sort contributions by the same order as the Indicator Trends table
    # on Page 1 (ALL_INDICATORS sequence). Unknown indicators go last.
    _order = {ind: idx for idx, ind in enumerate(ALL_INDICATORS)}
    sorted_contribs = sorted(contributions, key=lambda c: _order.get(c.indicator_id, 999))

    return MarketRegime(
        score=score,
        buy_points=buy,
        risk_points=risk,
        label=label,
        css_class=css,
        summary=summary,
        contributions=[
            {
                "indicator_id": c.indicator_id.value,
                "title": c.title,
                "value": c.value,
                "unit": c.unit,
                "tier": c.tier,
                "weight": c.weight,
                "points": c.points,
                "reason": c.reason,
            }
            for c in sorted_contribs
        ],
        coverage=len([c for c in contributions if c.tier != 0]),
        total=considered,
    )
