"""Adaptive market activation engine for v0.8.7.

This layer translates market/technical/catalyst conditions into CEO/operator
language. It does not use static canned advice: recommendations are selected
from the current market inputs, catalyst phase, technical setup, and capital-flow
read.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engines.classification_engine import ClassificationResult
from engines.relative_performance_engine import safe_return
from engines.technical_engine import TechnicalSnapshot


@dataclass(frozen=True)
class ActivationSummary:
    market_attention: str
    activation_state: str
    activation_score: float
    summary: str
    why_it_matters: str
    recommended_actions: list[str]
    watch_signal: str
    components: dict[str, float]
    triggered_paths: list[str]
    evidence: list[str]


def _score_from_spread(spread: float | None) -> float:
    if spread is None or pd.isna(spread):
        return 5.0
    spread = float(spread)
    if spread >= 8:
        return 8.5
    if spread >= 3:
        return 7.0
    if spread > -3:
        return 5.2
    if spread > -8:
        return 3.8
    return 2.5


def _score_from_text(text: str | None) -> float:
    if not text:
        return 5.0
    t = text.lower()
    if any(x in t for x in ["strong", "inflow", "constructive", "accelerating"]):
        return 7.2
    if any(x in t for x in ["weak", "outflow", "risk-off", "pressure"]):
        return 3.4
    if any(x in t for x in ["neutral", "mixed", "selective"]):
        return 5.0
    return 5.0


def _phase_score(phase: str | None) -> float:
    if not phase:
        return 5.0
    p = phase.lower()
    if "pre" in p:
        return 6.0
    if "near" in p:
        return 6.5
    if "post" in p:
        return 4.8
    return 5.0


def _label(score: float) -> str:
    if score >= 7.2:
        return "High"
    if score >= 5.4:
        return "Developing"
    if score >= 4.2:
        return "Low-to-developing"
    return "Low"


def build_activation_summary(
    return_table: pd.DataFrame,
    classification: ClassificationResult,
    technical_snapshot: TechnicalSnapshot | None,
    catalyst_phase: str | None,
    catalyst_positioning: str | None,
    adc_posture: str | None,
    alignment_label: str | None,
) -> ActivationSummary:
    """Build adaptive CEO communication / visibility guidance.

    The recommendation adapts to the data:
    - weak positioning + pre-catalyst -> visibility/narrative activation
    - improving technicals + catalyst -> amplify momentum
    - strong tape -> maintain disciplined cadence
    - risk-off tape -> education and context rather than promotional volume
    """

    nxtc_5d = safe_return(return_table, "NXTC", "5D %")
    nxtc_30d = safe_return(return_table, "NXTC", "30D %")
    spread_5d = classification.spread_5d_xbi
    spread_30d = classification.spread_30d_xbi

    relative_score = (_score_from_spread(spread_5d) * 0.55) + (_score_from_spread(spread_30d) * 0.45)
    technical_score = technical_snapshot.setup_score if technical_snapshot else 5.0
    catalyst_score = _phase_score(catalyst_phase)
    positioning_score = _score_from_text(catalyst_positioning or alignment_label)
    adc_score = _score_from_text(adc_posture)

    score = round(
        relative_score * 0.30
        + technical_score * 0.25
        + positioning_score * 0.20
        + adc_score * 0.15
        + catalyst_score * 0.10,
        1,
    )

    attention = _label(score)
    weak_relative = relative_score < 4.2
    weak_technical = technical_score < 4.8
    pre_catalyst = bool(catalyst_phase and "pre" in catalyst_phase.lower())
    adc_supportive = adc_score >= 5.8
    risk_off = "weak" in (classification.market_regime or "").lower() or "risk-off" in (catalyst_positioning or "").lower()

    triggered_paths: list[str] = []
    evidence: list[str] = []
    evidence.append(f"NXTC 5D return: {nxtc_5d:+.1f}%" if nxtc_5d is not None else "NXTC 5D return unavailable")
    evidence.append(f"NXTC 30D return: {nxtc_30d:+.1f}%" if nxtc_30d is not None else "NXTC 30D return unavailable")
    evidence.append(f"NXTC vs XBI 5D spread: {spread_5d:+.1f}%" if spread_5d is not None else "NXTC vs XBI 5D spread unavailable")
    evidence.append(f"NXTC vs XBI 30D spread: {spread_30d:+.1f}%" if spread_30d is not None else "NXTC vs XBI 30D spread unavailable")
    evidence.append(f"Technical setup score: {technical_score:.1f}/10")
    evidence.append(f"ADC theme support score: {adc_score:.1f}/10")
    evidence.append(f"Catalyst phase: {catalyst_phase or 'Unavailable'}")

    if weak_relative:
        triggered_paths.append("weak_relative_performance")
    if weak_technical:
        triggered_paths.append("weak_technical_setup")
    if pre_catalyst:
        triggered_paths.append("pre_catalyst_window")
    if adc_supportive:
        triggered_paths.append("adc_theme_supportive")
    if risk_off:
        triggered_paths.append("risk_off_context")

    if attention == "High":
        triggered_paths.append("high_attention_branch")
        activation_state = "Market is already paying attention"
        summary = "NXTC is showing enough market/technical confirmation that visibility work should reinforce existing momentum rather than manufacture attention from scratch."
        why = "When attention is already developing, the highest-value communication is clarity: explain the catalyst, why it matters, and what investors should watch next."
    elif pre_catalyst and (weak_relative or weak_technical):
        triggered_paths.append("underdeveloped_pre_catalyst_awareness_branch")
        activation_state = "Underdeveloped pre-catalyst awareness"
        summary = "NXTC has an upcoming catalyst, but the stock is not yet showing convincing market anticipation. This points to an attention gap, not a conclusion about the science."
        why = "In pre-catalyst periods, investors often position earlier when the story, timing, and relevance are repeatedly made clear. Weak tape plus low visibility can leave the market underprepared for the event."
    elif adc_supportive and weak_relative:
        triggered_paths.append("adc_theme_supportive_but_nxtc_lagging_branch")
        activation_state = "Theme is working, but NXTC is not yet participating"
        summary = "The broader ADC lane is more constructive than NXTC’s current tape, suggesting a narrative-bridging opportunity."
        why = "If investors are rewarding ADC exposure elsewhere but not NXTC, the communication opportunity is to make the connection between the broader ADC theme and NextCure’s CDH6/B7-H4 story easier to understand."
    elif risk_off:
        triggered_paths.append("risk_off_educational_visibility_branch")
        activation_state = "Risk-off environment; visibility needs to be educational"
        summary = "The market environment is not broadly supportive, so communications should focus on credibility, timing, and why the catalyst matters rather than promotional volume."
        why = "In weak biotech tapes, companies need to reduce uncertainty and help investors understand what could change the story."
    else:
        triggered_paths.append("selective_attention_branch")
        activation_state = "Selective attention; needs clearer confirmation"
        summary = "The setup is not broken, but attention is not broad enough yet. Communication should be steady, specific, and tied to measurable catalyst milestones."
        why = "The market is more likely to respond when narrative, timing, technical confirmation, and peer context begin lining up."

    actions: list[str] = []
    if attention == "High":
        actions.append("Maintain a disciplined investor-communication cadence that reinforces the catalyst, because the market is already showing signs of attention.")
        if technical_score >= 5.8:
            actions.append("Use improving technical confirmation as a cue to make the story easier for investors to follow, not as a reason to overpromote.")
    else:
        if pre_catalyst:
            actions.append("Make the upcoming SIM0505/CDH6 catalyst easier to understand: what is coming, why ovarian cancer matters, and what a positive readout could change.")
        if weak_relative or weak_technical:
            actions.append("Use investor-facing visibility to close the attention gap before the event; do not rely on the market to discover the story on its own.")
        if attention in {"Low", "Low-to-developing"}:
            actions.append("Consider a consistent LinkedIn/IR content cadence around the catalyst, mechanism, disease area, and investor timeline to build awareness without overpromising.")

    if adc_supportive:
        actions.append("Thread NextCure’s story into the broader ADC capital-flow theme so investors can connect NXTC to where the category is already being rewarded.")
    if risk_off:
        actions.append("Keep the tone educational and evidence-based; in a weak biotech tape, clarity and credibility matter more than aggressive promotion.")
    if technical_score >= 5.8 and attention != "High":
        actions.append("If technicals continue improving, amplify the narrative while the tape is beginning to confirm attention.")

    # De-duplicate while preserving order and cap for UI readability.
    seen = set()
    clean_actions = []
    for action in actions:
        if action not in seen:
            clean_actions.append(action)
            seen.add(action)
    clean_actions = clean_actions[:4]

    if weak_relative and weak_technical:
        watch = "Watch for the first evidence that awareness is translating into market behavior: stronger volume on up days, RSI/MACD stabilization, and NXTC narrowing the gap versus XBI and ADC/ovarian peers."
    elif adc_supportive and weak_relative:
        watch = "Watch whether NXTC starts participating in the same ADC strength visible in peer lanes. That would suggest the narrative bridge is starting to work."
    elif attention == "High":
        watch = "Watch for momentum quality: whether gains are supported by volume and whether NXTC continues outperforming XBI into the catalyst window."
    else:
        watch = "Watch whether visibility, catalyst timing, and technical confirmation begin aligning; one signal alone is not enough for conviction."

    return ActivationSummary(
        market_attention=attention,
        activation_state=activation_state,
        activation_score=score,
        summary=summary,
        why_it_matters=why,
        recommended_actions=clean_actions,
        watch_signal=watch,
        components={
            "Relative performance": round(relative_score, 1),
            "Technical setup": round(technical_score, 1),
            "Catalyst positioning": round(positioning_score, 1),
            "ADC theme support": round(adc_score, 1),
            "Catalyst timing": round(catalyst_score, 1),
        },
        triggered_paths=triggered_paths,
        evidence=evidence,
    )
