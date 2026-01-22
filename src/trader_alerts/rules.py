from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .constants import IndicatorId
from .models import Alert, AlertLevel, Observation


def _fmt(v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:.2f}%"
    if unit == "bp":
        return f"{v:.0f}bp"
    return f"{v:.4g}{unit}"


def _latest_value(obs: Observation | None) -> float | None:
    return None if obs is None else float(obs.value)


def _value_on_or_before(history: list[Observation], target: date) -> Observation | None:
    """
    history: 按 as_of 升序
    返回 <= target 的最后一个观测值
    """
    best: Observation | None = None
    for o in history:
        if o.as_of <= target:
            best = o
        else:
            break
    return best


def _delta(
    history: list[Observation],
    latest: Observation,
    lookback_days: int,
) -> float | None:
    """
    用“向前回看 lookback_days”近似月/年变化（对周/月频数据也适用）。
    """
    past = _value_on_or_before(history, latest.as_of.fromordinal(latest.as_of.toordinal() - lookback_days))
    if not past:
        return None
    return float(latest.value) - float(past.value)


@dataclass(frozen=True)
class RuleContext:
    latest: Observation | None
    history_30d: list[Observation]
    history_365d: list[Observation]


RuleFn = Callable[[RuleContext], Alert | None]


def rule_bofa_bull_bear(ctx: RuleContext) -> Alert | None:
    """
    注意：你已选择用 YCharts 的 AAII Bull-Bear Spread 替代 BofA Bull & Bear。
    这个指标单位是百分比（Bull% - Bear%），而非 0-10。

    简化阈值（可在此调整）：
    - <= -20%：极度悲观（反向）→ 牛市预警
    - >= +20%：极度乐观 → 熊市预警
    """
    latest = ctx.latest
    if not latest:
        return None
    v = float(latest.value)

    if v <= -20:
        return Alert(
            indicator_id=IndicatorId.BOFA_BULL_BEAR,
            level=AlertLevel.BULL,
            title="AAII Bull-Bear Spread 极度悲观（反向买入）",
            message="当 Bull-Bear Spread 很低（甚至为负）通常代表恐慌情绪更强，可能更接近反弹窗口。",
            evidence={"value": v, "unit": latest.unit},
        )
    if v >= 20:
        return Alert(
            indicator_id=IndicatorId.BOFA_BULL_BEAR,
            level=AlertLevel.BEAR,
            title="AAII Bull-Bear Spread 极度乐观（过热风险）",
            message="当 Bull-Bear Spread 很高通常代表情绪偏亢奋，回撤风险上升。",
            evidence={"value": v, "unit": latest.unit},
        )

    return Alert(
        indicator_id=IndicatorId.BOFA_BULL_BEAR,
        level=AlertLevel.NEUTRAL,
        title="AAII Bull-Bear Spread 中性",
        message="未触发极值阈值。",
        evidence={"value": v, "unit": latest.unit},
    )


def rule_hy_spread(ctx: RuleContext) -> Alert | None:
    """
    高收益债利差（OAS）常见阈值（经验）：
    - >=500bp：信用压力显著 → 熊市预警
    - <=300bp：信用环境偏好 → 牛市预警
    - 1个月扩大 >=100bp：快速恶化 → 熊市预警
    - 1个月收窄 >=100bp：快速修复 → 牛市预警
    """
    latest = ctx.latest
    if not latest:
        return None
    v = float(latest.value)
    d30 = _delta(ctx.history_365d, latest, 30)

    if v >= 500 or (d30 is not None and d30 >= 100):
        return Alert(
            indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
            level=AlertLevel.BEAR,
            title="高收益债利差走阔（信用压力）",
            message="利差走阔通常代表风险补偿上升与信用担忧加剧，往往对股市不利。",
            evidence={"value": v, "unit": latest.unit, "delta_1m": d30},
        )

    if v <= 300 or (d30 is not None and d30 <= -100):
        return Alert(
            indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
            level=AlertLevel.BULL,
            title="高收益债利差收窄（信用改善）",
            message="利差收窄通常代表风险偏好修复，对风险资产更友好。",
            evidence={"value": v, "unit": latest.unit, "delta_1m": d30},
        )

    return Alert(
        indicator_id=IndicatorId.US_HIGH_YIELD_SPREAD,
        level=AlertLevel.NEUTRAL,
        title="高收益债利差中性",
        message="未触发信用压力/修复阈值。",
        evidence={"value": v, "unit": latest.unit, "delta_1m": d30},
    )


RULES: dict[IndicatorId, RuleFn] = {
    IndicatorId.BOFA_BULL_BEAR: rule_bofa_bull_bear,
    IndicatorId.US_HIGH_YIELD_SPREAD: rule_hy_spread,
}


def rule_sp500_pe_ratio(ctx: RuleContext) -> Alert | None:
    """
    估值预警（非常简化，可自行调整）：
    - PE >= 25：估值偏贵/过热 → 熊市预警
    - PE <= 15：估值偏便宜 → 牛市预警
    """
    latest = ctx.latest
    if not latest:
        return None
    v = float(latest.value)
    if v >= 25:
        return Alert(
            indicator_id=IndicatorId.SP500_PE_RATIO,
            level=AlertLevel.BEAR,
            title="S&P 500 PE 偏高（估值过热风险）",
            message="PE 仅是估值维度之一；高估值会放大回撤敏感性，需结合利率/盈利周期判断。",
            evidence={"value": v, "unit": latest.unit},
        )
    if v <= 15:
        return Alert(
            indicator_id=IndicatorId.SP500_PE_RATIO,
            level=AlertLevel.BULL,
            title="S&P 500 PE 偏低（估值更友好）",
            message="低估值通常代表更高的安全边际，但仍需结合盈利下修风险判断。",
            evidence={"value": v, "unit": latest.unit},
        )
    return Alert(
        indicator_id=IndicatorId.SP500_PE_RATIO,
        level=AlertLevel.NEUTRAL,
        title="S&P 500 PE 中性",
        message="未触发估值阈值。",
        evidence={"value": v, "unit": latest.unit},
    )


RULES[IndicatorId.SP500_PE_RATIO] = rule_sp500_pe_ratio


def rule_cnn_fear_greed(ctx: RuleContext) -> Alert | None:
    """
    CNN Fear & Greed Index（0-100）常用分区：
    - <=25：Extreme Fear（反向）→ 牛市预警
    - >=75：Extreme Greed → 熊市预警
    """
    latest = ctx.latest
    if not latest:
        return None
    v = float(latest.value)
    rating = (latest.meta or {}).get("rating")

    if v <= 25:
        return Alert(
            indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
            level=AlertLevel.BULL,
            title="CNN Fear & Greed：极度恐惧（反向买入）",
            message="情绪极度恐惧时更容易接近阶段性底部/反弹窗口（建议结合信用利差与趋势确认）。",
            evidence={"value": v, "unit": latest.unit, "rating": rating},
        )
    if v >= 75:
        return Alert(
            indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
            level=AlertLevel.BEAR,
            title="CNN Fear & Greed：极度贪婪（过热风险）",
            message="情绪极度贪婪往往伴随拥挤交易，回撤风险上升。",
            evidence={"value": v, "unit": latest.unit, "rating": rating},
        )
    return Alert(
        indicator_id=IndicatorId.CNN_FEAR_GREED_INDEX,
        level=AlertLevel.NEUTRAL,
        title="CNN Fear & Greed：中性区间",
        message="未触发极端阈值。",
        evidence={"value": v, "unit": latest.unit, "rating": rating},
    )


RULES[IndicatorId.CNN_FEAR_GREED_INDEX] = rule_cnn_fear_greed


