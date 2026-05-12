"""Technical + catalyst alignment engine for v0.8."""

from __future__ import annotations

from dataclasses import dataclass

from engines.catalyst_timing_engine import CatalystTimingSummary
from engines.technical_engine import TechnicalSnapshot


@dataclass(frozen=True)
class AlignmentSummary:
    label: str
    color_state: str
    explanation: str
    what_it_means: str
    watch: list[str]


def build_alignment_summary(
    nxtc_technical: TechnicalSnapshot | None,
    catalyst_timing: CatalystTimingSummary | None,
    capital_posture: str | None = None,
) -> AlignmentSummary:
    if nxtc_technical is None or catalyst_timing is None:
        return AlignmentSummary(
            label="Unavailable",
            color_state="neutral",
            explanation="Technical/catalyst alignment could not be evaluated.",
            what_it_means="Need both technical data and catalyst timing to evaluate the setup.",
            watch=["Restore NXTC price history", "Confirm primary catalyst timing"],
        )

    score = nxtc_technical.setup_score
    timing = catalyst_timing.nxtc_timing.lower()
    cap = (capital_posture or "").lower()
    near = "asco" in timing or "q2" in timing or "near" in timing
    cap_good = "strong" in cap or "constructive" in cap
    cap_bad = "weak" in cap or "outflow" in cap or "risk-off" in cap

    if near and score >= 6.5 and not cap_bad:
        label = "Bullish pre-catalyst alignment"
        color = "positive"
        explanation = "Defined catalyst timing plus improving technicals creates a credible pre-event setup."
        meaning = "The market may be starting to reward the story before data; watch whether volume confirms accumulation."
    elif near and score >= 5.2:
        label = "Neutral catalyst setup"
        color = "neutral"
        explanation = "The catalyst is defined, but technical confirmation is only partial."
        meaning = "The event matters, but the market has not yet fully committed ahead of it."
    elif near and score < 5.2:
        label = "Weak pre-catalyst positioning"
        color = "caution"
        explanation = "NXTC has a defined catalyst, but the stock setup remains technically weak."
        meaning = "The burden of proof is on buyers. A catalyst can still matter, but current trading does not show strong anticipation."
    elif score >= 6.5:
        label = "Technical improvement without defined event pressure"
        color = "neutral"
        explanation = "Technicals are improving, but timing is not clearly anchored to a near-term event."
        meaning = "This is more of a market/technical setup than a catalyst-driven setup."
    else:
        label = "Unconfirmed setup"
        color = "neutral"
        explanation = "Neither technicals nor catalyst timing create a clean near-term alignment yet."
        meaning = "The dashboard should keep this in watch mode until either price structure or event timing improves."

    watch = [
        "Price reclaiming EMA20/EMA50 with improving volume",
        "MACD histogram turning positive or expanding",
        "Peer ADC lane strengthening into the same window",
        "Any company communication that clarifies catalyst timing or data expectations",
    ]
    return AlignmentSummary(label=label, color_state=color, explanation=explanation, what_it_means=meaning, watch=watch)
