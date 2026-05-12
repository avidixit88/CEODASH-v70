"""Corporate strategy timing engine.

This output is intentionally positioned as corporate strategy intelligence, not
trading advice. It helps a CEO think about outreach, communication cadence, and
what to watch before catalysts.
"""

from __future__ import annotations

from dataclasses import dataclass

from engines.capital_flow_engine import CapitalFlowSummary
from engines.classification_engine import ClassificationResult
from engines.market_regime_engine import MarketRegimeSummary
from engines.window_score_engine import WindowScoreSummary


@dataclass(frozen=True)
class StrategySummary:
    suggested_actions: list[str]
    press_timing: str
    watch_items: list[str]


def build_strategy_summary(
    regime: MarketRegimeSummary,
    score: WindowScoreSummary,
    classification: ClassificationResult | None,
    capital_summary: CapitalFlowSummary | None,
    primary_catalyst_phase: str,
) -> StrategySummary:
    actions: list[str] = []
    watch: list[str] = []

    if score.score >= 7.5:
        actions.append("Lean into investor education while the ADC and NXTC relative backdrop is favorable.")
        actions.append("Prepare catalyst-adjacent messaging so positive data can be contextualized quickly.")
    elif score.score >= 6.0:
        actions.append("Use measured investor outreach, but do not assume the market is broadly supportive yet.")
        actions.append("Use peer read-through selectively; emphasize where NXTC is differentiated rather than generic ADC enthusiasm.")
    else:
        actions.append("Keep investor messaging disciplined; the current window is not strong enough for aggressive narrative amplification.")
        actions.append("Monitor for a better setup before attempting major narrative amplification.")

    if classification and classification.nxtc_vs_xbi == "Outperforming":
        actions.append("Highlight stock-specific strength versus XBI as evidence the market is differentiating NXTC.")
        watch.append("Watch whether outperformance persists beyond the short-term 5D window.")
    elif classification and classification.nxtc_vs_xbi == "Underperforming":
        actions.append("Prioritize explaining the upcoming SIM0505 catalyst clearly because current stock action is not yet validating the story.")
        watch.append("Watch for reversal from underperformance before assuming pre-catalyst accumulation.")

    if capital_summary and "Outflow" in capital_summary.adc_posture:
        watch.append("ADC channel outflow could reduce read-through support even if NXTC-specific news is positive.")
    else:
        watch.append("ADC channel strength should be monitored as supportive read-through into SIM0505/B7-H4 narrative windows.")

    phase = (primary_catalyst_phase or "").lower()
    if "pre" in phase and score.score >= 6.0:
        press_timing = "Near-term window is constructive; prepare communications for the next 2-4 weeks while avoiding over-hype before data."
    elif "pre" in phase:
        press_timing = "Pre-catalyst setup exists, but current positioning is not strong enough to lean heavily into press cadence without confirmation."
    elif "post" in phase:
        press_timing = "Post-catalyst period: focus on explaining data quality, next steps, and investor follow-through."
    else:
        press_timing = "Timing should remain catalyst-aware and market-confirmed rather than calendar-driven."

    watch.append("Acceleration into catalyst window versus early exhaustion or sell-the-news behavior.")
    return StrategySummary(actions[:4], press_timing, watch[:4])
