"""Market window score engine.

The score is intentionally transparent: it synthesizes sector trend, ADC channel
strength, NXTC relative strength, and catalyst phase into a 0-10 CEO-readable
score.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engines.capital_flow_engine import CapitalFlowSummary
from engines.classification_engine import ClassificationResult
from engines.market_regime_engine import MarketRegimeSummary
from engines.relative_performance_engine import safe_return


@dataclass(frozen=True)
class WindowScoreSummary:
    score: float
    label: str
    interpretation: str
    components: dict[str, float]


def _bounded(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return max(low, min(high, value))


def _return_component(value: object) -> float:
    if value is None or pd.isna(value):
        return 5.0
    val = float(value)
    return _bounded(5.0 + val / 3.0)


def _posture_component(posture: str) -> float:
    posture = (posture or "").lower()
    if "strong" in posture:
        return 8.5
    if "constructive" in posture:
        return 7.0
    if "balanced" in posture or "neutral" in posture:
        return 5.5
    if "selective outflow" in posture or "weak" in posture:
        return 3.5
    if "broad outflow" in posture or "risk-off" in posture:
        return 2.0
    return 5.0


def _relative_component(classification: ClassificationResult | None) -> float:
    if classification is None:
        return 5.0
    if classification.nxtc_vs_xbi == "Outperforming":
        return 8.0
    if classification.nxtc_vs_xbi == "Underperforming":
        return 3.0
    return 5.5


def build_market_window_score(
    return_table: pd.DataFrame,
    classification: ClassificationResult | None,
    capital_summary: CapitalFlowSummary | None,
    regime: MarketRegimeSummary | None,
    catalyst_phase: str | None = None,
) -> WindowScoreSummary:
    xbi_30 = safe_return(return_table, "XBI", "30D %")
    xbi_90 = safe_return(return_table, "XBI", "90D %")
    sector_component = (_return_component(xbi_30) * 0.65) + (_return_component(xbi_90) * 0.35)
    adc_component = _posture_component(capital_summary.adc_posture if capital_summary else "")
    nxtc_component = _relative_component(classification)

    phase = (catalyst_phase or "").lower()
    if "pre" in phase:
        catalyst_component = 7.0
    elif "event" in phase or "in-catalyst" in phase:
        catalyst_component = 6.0
    elif "post" in phase:
        catalyst_component = 4.5
    else:
        catalyst_component = 5.0

    risk_penalty = 0.0
    if regime and regime.risk_level == "High":
        risk_penalty = 1.0
    elif regime and regime.risk_level == "Moderate-High":
        risk_penalty = 0.5

    score = _bounded(
        sector_component * 0.25
        + adc_component * 0.30
        + nxtc_component * 0.30
        + catalyst_component * 0.15
        - risk_penalty
    )
    score = round(score, 1)
    nxtc_5 = safe_return(return_table, "NXTC", "5D %")
    nxtc_90 = safe_return(return_table, "NXTC", "90D %")
    if nxtc_90 is not None and not pd.isna(nxtc_90) and nxtc_5 is not None and not pd.isna(nxtc_5):
        if float(nxtc_90) > 0 and float(nxtc_5) >= 0:
            label = "Strong (accelerating)"
            interpretation = "Window definition: the quarterly trend is positive and short-term movement is also positive, so the stock is accelerating with the longer-term tape."
        elif float(nxtc_90) > 0 and float(nxtc_5) < 0:
            label = "Strong (pullback)"
            interpretation = "Window definition: the quarterly trend is still positive, but short-term weakness means this is a pullback inside a stronger tape."
        elif float(nxtc_90) < 0 and float(nxtc_5) > 0:
            label = "Weak (bounce attempt)"
            interpretation = "Window definition: the quarterly trend is negative, but short-term strength suggests a bounce attempt rather than a confirmed turn."
        elif float(nxtc_90) < 0 and float(nxtc_5) <= 0:
            label = "Weak (continuation)"
            interpretation = "Window definition: both the quarterly trend and short-term movement are negative, so the tape is still working against NXTC."
        else:
            label = "Neutral (conflicting signals)"
            interpretation = "Window definition: the signal mix is not aligned enough to call the setup clearly strong or weak."
    elif score >= 7.5:
        label = "Strong (data-limited)"
        interpretation = "Window definition: the composite score is favorable, but the timeframe alignment data is incomplete."
    elif score >= 6.0:
        label = "Neutral (constructive but selective)"
        interpretation = "Window definition: some inputs are supportive, but the environment is not broadly favorable enough for a clean strong-window label."
    elif score >= 4.0:
        label = "Neutral (conflicting signals)"
        interpretation = "Window definition: the market is not clearly helping NXTC, so catalyst clarity matters more than timing alone."
    else:
        label = "Weak (risk-off)"
        interpretation = "Window definition: sector or channel weakness may blunt the impact of good news."

    return WindowScoreSummary(
        score=score,
        label=label,
        interpretation=interpretation,
        components={
            "Sector": round(sector_component, 1),
            "ADC": round(adc_component, 1),
            "NXTC Relative": round(nxtc_component, 1),
            "Catalyst": round(catalyst_component, 1),
        },
    )
