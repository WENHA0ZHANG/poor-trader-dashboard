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
)


