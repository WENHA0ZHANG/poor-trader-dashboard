from __future__ import annotations

from enum import Enum


class IndicatorId(str, Enum):
    # AAII Bull-Bear Spread (from YCharts; occupies original "bofa_bull_bear" slot)
    BOFA_BULL_BEAR = "bofa_bull_bear"

    # US High Yield Bond Spread (primary data source: TradingEconomics)
    US_HIGH_YIELD_SPREAD = "us_high_yield_spread"

    # Extra) Valuation (public webpage)
    SP500_PE_RATIO = "sp500_pe_ratio"

    # Extra) Valuation (public webpage)
    NASDAQ100_PE_RATIO = "nasdaq100_pe_ratio"

    # Extra) Sentiment (public JSON endpoint)
    CNN_FEAR_GREED_INDEX = "cnn_fear_greed_index"

    # Extra) Options sentiment (CNN component)
    CNN_PUT_CALL_OPTIONS = "cnn_put_call_options"

    # Extra) Technical (public webpage)
    SP500_RSI = "sp500_rsi"

    # Extra) Breadth (public webpage)
    NASDAQ100_ABOVE_20D_MA = "nasdaq100_above_20d_ma"

    # Extra) Volatility (CNN Fear & Greed page)
    VIX = "vix"

    # Extra) Tail-risk hedging cost (CBOE SKEW, via Yahoo ^SKEW).
    # Rises when institutions pay up for far-OTM puts; sustained >145 has
    # often preceded sharp drawdowns (early 2020, late 2021, summer 2024).
    CBOE_SKEW = "cboe_skew"

    # Extra) Yield curve – 10Y minus 2Y Treasury yield (FRED T10Y2Y).
    # Inversion <0% has preceded every U.S. recession since 1980; the
    # rapid re-steepening (move from negative back through 0) tends to
    # mark the late-cycle window where bear markets actually hit.
    YC_10Y_2Y = "yc_10y_2y"


ALL_INDICATORS: tuple[IndicatorId, ...] = (
    IndicatorId.BOFA_BULL_BEAR,                    # Investor Sentiment Bull-Bear Spread
    IndicatorId.CNN_FEAR_GREED_INDEX,             # Fear & Greed Index
    IndicatorId.CNN_PUT_CALL_OPTIONS,             # Put/Call Ratio (5-Day Average)
    IndicatorId.VIX,                              # S&P 500 Volatility Index
    IndicatorId.SP500_RSI,                        # S&P 500 Relative Strength Index
    IndicatorId.SP500_PE_RATIO,                   # S&P 500 Price-to-Earnings Ratio
    IndicatorId.NASDAQ100_PE_RATIO,               # Nasdaq 100 Price-to-Earnings Ratio
    IndicatorId.NASDAQ100_ABOVE_20D_MA,           # Nasdaq 100 Above 20-Day Moving Average (%)
    IndicatorId.US_HIGH_YIELD_SPREAD,             # US High Yield Option-Adjusted Spread
    IndicatorId.CBOE_SKEW,                        # CBOE SKEW (tail-risk hedging)
    IndicatorId.YC_10Y_2Y,                        # 10Y-2Y Treasury yield curve
)


