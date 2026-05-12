"""Scenario engine for forward-looking CEO watch cases."""

from __future__ import annotations

from engines.capital_flow_engine import CapitalFlowSummary
from engines.classification_engine import ClassificationResult
from engines.market_regime_engine import MarketRegimeSummary
from engines.window_score_engine import WindowScoreSummary


def build_scenario_outlook(
    regime: MarketRegimeSummary,
    score: WindowScoreSummary,
    classification: ClassificationResult | None,
    capital_summary: CapitalFlowSummary | None,
) -> list[dict[str, str]]:
    scenarios: list[dict[str, str]] = []

    if classification and classification.nxtc_vs_xbi == "Outperforming":
        scenarios.append({
            "Scenario": "NXTC continues outperforming XBI",
            "Implication": "Supports a pre-catalyst accumulation read and gives investor outreach more leverage.",
            "Watch": "Confirm with 30D trend and volume rather than only a short 5D move.",
        })
    else:
        scenarios.append({
            "Scenario": "NXTC begins outperforming XBI",
            "Implication": "Would shift the story from sector sympathy to stock-specific investor interest.",
            "Watch": "Look for sustained relative strength across 5D and 30D windows.",
        })

    adc_posture = capital_summary.adc_posture if capital_summary else "Unavailable"
    if "Strong" in adc_posture or "Constructive" in adc_posture:
        scenarios.append({
            "Scenario": "ADC channel remains constructive",
            "Implication": "B7-H4/CDH6 read-through stays supportive and can amplify NXTC catalyst positioning.",
            "Watch": "Large-cap ADC peers and ovarian ADC comparators for sympathy strength or fade.",
        })
    else:
        scenarios.append({
            "Scenario": "ADC channel weakens further",
            "Implication": "Even good company-specific progress may receive less market credit if the modality lane loses sponsorship.",
            "Watch": "Channel score turning from outflow to balanced before increasing communication intensity.",
        })

    if regime.biotech_regime in {"Weak", "Risk-Off"}:
        scenarios.append({
            "Scenario": "XBI remains risk-off",
            "Implication": "Sector pressure can overwhelm company-specific progress and compress financing windows.",
            "Watch": "XBI 30D/90D stabilization before assuming market support.",
        })
    else:
        scenarios.append({
            "Scenario": "Biotech tape stays stable",
            "Implication": "Gives NXTC a cleaner backdrop for clinical narrative and catalyst preparation.",
            "Watch": "Whether small-cap oncology breadth participates or only large caps are moving.",
        })

    if score.score >= 6.0:
        watch = "A drop below Selective should reduce press/aggressive outreach intensity."
    else:
        watch = "Improvement into Selective or Favorable would support more active outreach."
    scenarios.append({
        "Scenario": f"Market Window Score holds {score.label}",
        "Implication": score.interpretation,
        "Watch": watch,
    })
    return scenarios
