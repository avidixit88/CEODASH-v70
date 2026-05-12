"""Market regime engine for CEO-level timing intelligence.

This module intentionally keeps the logic explainable. The objective is not to
produce a black-box trading signal; it creates a corporate strategy readout that
combines biotech market posture, ADC channel strength, and NXTC relative action.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engines.capital_flow_engine import CapitalFlowSummary
from engines.classification_engine import ClassificationResult
from engines.relative_performance_engine import safe_return


@dataclass(frozen=True)
class MarketRegimeSummary:
    biotech_regime: str
    growth_regime: str
    adc_regime: str
    nxtc_regime: str
    combined_read: str
    risk_level: str


def _classify_return(value: object, strong: float = 7.5, constructive: float = 2.0, weak: float = -2.0, severe: float = -7.5) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    val = float(value)
    if val >= strong:
        return "Strong"
    if val >= constructive:
        return "Constructive"
    if val <= severe:
        return "Risk-Off"
    if val <= weak:
        return "Weak"
    return "Neutral"


def _posture_to_regime(posture: str) -> str:
    """Translate channel capital-flow wording into a Strategy & Timing regime.

    The capital-flow engine intentionally uses human language such as
    "Longer-term inflow" or "No clear flow." Strategy & Timing should never
    show "Unavailable" when that language is present; it should extrapolate a
    clean regime from the available channel read.
    """
    normalized = (posture or "").lower().strip()
    if not normalized or "unavailable" in normalized:
        return "Unavailable"
    if "strong" in normalized or "longer-term inflow" in normalized:
        return "Strong"
    if "selective inflow" in normalized or "rebound" in normalized or "improving" in normalized:
        return "Constructive"
    if "outflow" in normalized or "fade" in normalized or "soft" in normalized:
        return "Weak"
    if "no clear" in normalized or "neutral" in normalized or "balanced" in normalized:
        return "Neutral"
    if "inflow" in normalized:
        return "Constructive"
    return "Neutral"


def summarize_market_regime(
    return_table: pd.DataFrame,
    classification: ClassificationResult | None,
    capital_summary: CapitalFlowSummary | None,
) -> MarketRegimeSummary:
    xbi_30 = safe_return(return_table, "XBI", "30D %")
    xbi_90 = safe_return(return_table, "XBI", "90D %")
    qqq_30 = safe_return(return_table, "QQQ", "30D %")
    qqq_90 = safe_return(return_table, "QQQ", "90D %")
    nxtc_30 = safe_return(return_table, "NXTC", "30D %")
    nxtc_90 = safe_return(return_table, "NXTC", "90D %")

    biotech_score = None
    if xbi_30 is not None and xbi_90 is not None and not pd.isna(xbi_30) and not pd.isna(xbi_90):
        biotech_score = 0.6 * float(xbi_30) + 0.4 * float(xbi_90)
    growth_score = None
    if qqq_30 is not None and qqq_90 is not None and not pd.isna(qqq_30) and not pd.isna(qqq_90):
        growth_score = 0.6 * float(qqq_30) + 0.4 * float(qqq_90)
    nxtc_score = None
    if nxtc_30 is not None and nxtc_90 is not None and not pd.isna(nxtc_30) and not pd.isna(nxtc_90):
        nxtc_score = 0.55 * float(nxtc_30) + 0.45 * float(nxtc_90)

    biotech_regime = _classify_return(biotech_score)
    growth_regime = _classify_return(growth_score)
    adc_regime = _posture_to_regime(capital_summary.adc_posture if capital_summary else "Unavailable")

    if classification is not None and classification.nxtc_vs_xbi == "Outperforming XBI":
        nxtc_regime = "Company-Specific Strength"
    elif classification is not None and classification.nxtc_vs_xbi == "Underperforming XBI":
        nxtc_regime = "Company-Specific Weakness"
    else:
        nxtc_regime = _classify_return(nxtc_score)

    if biotech_regime in {"Constructive", "Strong"} and adc_regime in {"Constructive", "Strong"} and "Strength" in nxtc_regime:
        combined = "Favorable window: biotech, ADC capital flow, and NXTC relative action are aligned."
        risk = "Moderate"
    elif adc_regime in {"Constructive", "Strong"} and "Strength" in nxtc_regime:
        combined = "Selective window: ADC/NXTC setup is better than the broader biotech tape."
        risk = "Moderate-High"
    elif biotech_regime in {"Weak", "Risk-Off"}:
        combined = "Cautious window: sector pressure may overwhelm company-specific progress."
        risk = "High"
    else:
        combined = "Neutral window (conflicting signals): some inputs are supportive, but the broader setup is not aligned enough to call the environment favorable. Catalyst clarity and technical confirmation matter more than timing alone."
        risk = "Moderate"

    return MarketRegimeSummary(
        biotech_regime=biotech_regime,
        growth_regime=growth_regime,
        adc_regime=adc_regime,
        nxtc_regime=nxtc_regime,
        combined_read=combined,
        risk_level=risk,
    )
