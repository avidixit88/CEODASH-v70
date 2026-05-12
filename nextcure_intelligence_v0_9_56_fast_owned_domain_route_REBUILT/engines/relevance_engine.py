"""Strategic relevance engine v0.9.2.

This engine converts incoming or curated signals into NextCure-specific
intelligence. It is deliberately source-agnostic: today it can score curated seed
signals; later the same contract can accept patents, grants, abstracts, PRs, SEC
filings, or clinical-trial updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import re

import pandas as pd

from config.strategic_interests import CURATED_SIGNAL_SEEDS, NEXTCURE_PROFILE, StrategicInterestProfile


@dataclass(frozen=True)
class RelevanceSignal:
    source_type: str
    headline: str
    entities: str
    relevance_score: float
    relevance_tier: str
    matched_profile_terms: tuple[str, ...]
    signal_class: str
    why_relevant: str
    strategic_question: str
    recommended_next_source: str
    executive_takeaway: str


@dataclass(frozen=True)
class StrategicRelevanceSummary:
    headline: str
    executive_brief: list[str]
    signal_table: pd.DataFrame
    theme_table: pd.DataFrame
    query_map: pd.DataFrame
    highest_priority_signals: list[RelevanceSignal]
    next_questions: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    haystack = _normalize(text)
    found: list[str] = []
    for term in terms:
        needle = _normalize(term)
        if needle and needle in haystack:
            found.append(term)
    return tuple(dict.fromkeys(found))


def _classify_signal(source_type: str, matched: tuple[str, ...], profile: StrategicInterestProfile) -> str:
    matched_lower = {_normalize(x) for x in matched}
    primary = {_normalize(x) for x in profile.primary_targets + profile.primary_indications}
    side = {_normalize(x) for x in profile.side_channels + profile.secondary_targets}
    tech = {_normalize(x) for x in profile.value_drivers}
    if matched_lower & primary:
        return "Direct pipeline relevance"
    if matched_lower & side:
        return "Side-channel optionality"
    if matched_lower & tech or "patent" in source_type.lower() or "technology" in source_type.lower():
        return "Differentiation trend"
    return "General strategic watch"


def _score_signal(text: str, matched: tuple[str, ...], profile: StrategicInterestProfile) -> float:
    score = 0.0
    normalized_text = _normalize(text)
    for term in profile.primary_targets:
        if _normalize(term) in normalized_text:
            score += 3.0
    for term in profile.primary_indications:
        if _normalize(term) in normalized_text:
            score += 2.0
    for term in profile.modalities:
        if _normalize(term) in normalized_text:
            score += 1.75
    for term in profile.secondary_targets + profile.side_channels:
        if _normalize(term) in normalized_text:
            score += 1.4
    for term in profile.value_drivers:
        if _normalize(term) in normalized_text:
            score += 1.0
    # Novelty / source-type boosts. These are intentionally modest so relevance
    # still comes mostly from profile overlap.
    if any(word in normalized_text for word in ["patent", "grant", "nih", "sbir", "abstract"]):
        score += 1.0
    if len(matched) >= 5:
        score += 0.75
    return round(min(score, 10.0), 1)


def _tier(score: float) -> str:
    if score >= 8:
        return "High"
    if score >= 5:
        return "Moderate"
    return "Watch"


def _executive_takeaway(signal_class: str, headline: str, strategic_question: str) -> str:
    if signal_class == "Direct pipeline relevance":
        return f"Pipeline-relevant signal: {headline} The operating question is: {strategic_question}"
    if signal_class == "Side-channel optionality":
        return f"Optionality signal: {headline} Keep it separate from the core oncology read unless external validation increases."
    if signal_class == "Differentiation trend":
        return f"Competitive-edge signal: {headline} This should feed messaging around differentiation, not just data collection."
    return f"Watch signal: {headline}"


def build_relevance_intelligence(
    incoming_signals: tuple[dict[str, str], ...] | list[dict[str, str]] | None = None,
    profile: StrategicInterestProfile = NEXTCURE_PROFILE,
) -> StrategicRelevanceSummary:
    seeds = list(incoming_signals or CURATED_SIGNAL_SEEDS)
    scored: list[RelevanceSignal] = []

    for raw in seeds:
        source_type = str(raw.get("source_type", "Manual signal"))
        headline = str(raw.get("headline", ""))
        entities = str(raw.get("entities", ""))
        why = str(raw.get("why_relevant", ""))
        question = str(raw.get("strategic_question", ""))
        next_source = str(raw.get("recommended_next_source", ""))
        full_text = " ".join([source_type, headline, entities, why, question, next_source])
        matched = _matches(full_text, profile.watch_terms + profile.value_drivers)
        score = _score_signal(full_text, matched, profile)
        signal_class = _classify_signal(source_type, matched, profile)
        scored.append(
            RelevanceSignal(
                source_type=source_type,
                headline=headline,
                entities=entities,
                relevance_score=score,
                relevance_tier=_tier(score),
                matched_profile_terms=matched,
                signal_class=signal_class,
                why_relevant=why,
                strategic_question=question,
                recommended_next_source=next_source,
                executive_takeaway=_executive_takeaway(signal_class, headline, question),
            )
        )

    scored = sorted(scored, key=lambda s: s.relevance_score, reverse=True)

    signal_table = pd.DataFrame([
        {
            "Source Type": s.source_type,
            "Headline / Incoming Signal": s.headline,
            "Relevance": s.relevance_tier,
            "Score": s.relevance_score,
            "Signal Class": s.signal_class,
            "Matched Terms": ", ".join(s.matched_profile_terms),
            "Why It Matters": s.why_relevant,
            "Strategic Question": s.strategic_question,
            "Next Source To Watch": s.recommended_next_source,
        }
        for s in scored
    ])

    theme_counter: Counter[str] = Counter()
    for s in scored:
        for term in s.matched_profile_terms:
            theme_counter[term] += 1
    theme_table = pd.DataFrame([
        {
            "Theme": theme,
            "Signal Count": count,
            "Interpretation": _theme_interpretation(theme, count),
        }
        for theme, count in theme_counter.most_common(10)
    ])

    query_map = pd.DataFrame([
        {
            "Source": "Patents",
            "Relevant Query Focus": "CDH6 OR B7-H4 + ADC + payload/linker/toxicity/patient selection",
            "Why It Matters": "Find competitive claims before they become investor-deck language.",
            "Synthesis Output": "Threat, validation, whitespace, or messaging-gap signal.",
        },
        {
            "Source": "Grants",
            "Relevant Query Focus": "Siglec-15, ApoE4, ovarian ADC, bone disease, NIH/SBIR/foundation funding",
            "Why It Matters": "Detect non-dilutive validation and academic momentum around side-channel assets.",
            "Synthesis Output": "External validation, partnering optionality, or emerging translational cluster.",
        },
        {
            "Source": "Conference abstracts",
            "Relevant Query Focus": "CDH6, B7-H4, gynecologic ADC, platinum-resistant ovarian cancer",
            "Why It Matters": "Abstract wording often reveals the differentiation narrative before the market fully digests it.",
            "Synthesis Output": "Read-through pressure, category validation, or competitor positioning change.",
        },
        {
            "Source": "Company PR / SEC filings",
            "Relevant Query Focus": "Financing, partnership, trial expansion, Fast Track, dose optimization, runway",
            "Why It Matters": "Connect market movement to financing windows and investor confidence.",
            "Synthesis Output": "Actionability around communication cadence, capital timing, and visibility gaps.",
        },
    ])

    top = scored[0] if scored else None
    headline = (
        f"Strategic Relevance Engine: top priority is {top.signal_class.lower()} around {', '.join(top.matched_profile_terms[:3])}."
        if top else
        "Strategic Relevance Engine: no scored signals available."
    )

    executive_brief = _build_executive_brief(scored, theme_table)
    next_questions = [s.strategic_question for s in scored[:4] if s.strategic_question]
    next_questions.append("Which new patent, grant, abstract, or PR changes our interpretation rather than merely adding another data point?")

    return StrategicRelevanceSummary(
        headline=headline,
        executive_brief=executive_brief,
        signal_table=signal_table,
        theme_table=theme_table,
        query_map=query_map,
        highest_priority_signals=scored[:3],
        next_questions=list(dict.fromkeys(next_questions)),
    )


def _theme_interpretation(theme: str, count: int) -> str:
    if theme in {"CDH6", "B7-H4", "ADC", "ovarian"}:
        return f"Core oncology relevance appeared in {count} signal(s); prioritize direct competitive read-through."
    if theme in {"Siglec-15", "ApoE4", "Alzheimer", "bone disease", "osteogenesis imperfecta"}:
        return f"Side-channel relevance appeared in {count} signal(s); track for partnering or grant validation."
    if theme in {"payload", "linker", "toxicity", "biomarker strategy", "patient selection"}:
        return f"Differentiation language appeared in {count} signal(s); this can shape messaging and competitive edge analysis."
    return f"Theme appeared in {count} signal(s); keep in watch mode until repeated or tied to a catalyst."


def _build_executive_brief(scored: list[RelevanceSignal], theme_table: pd.DataFrame) -> list[str]:
    if not scored:
        return ["No relevance-scored signals are available yet."]
    direct = [s for s in scored if s.signal_class == "Direct pipeline relevance"]
    side = [s for s in scored if s.signal_class == "Side-channel optionality"]
    diff = [s for s in scored if s.signal_class == "Differentiation trend"]
    brief: list[str] = []
    if direct:
        brief.append(f"Direct pipeline relevance: {direct[0].headline} This is the highest-value signal class because it can change how SIM0505 is benchmarked.")
    if diff:
        brief.append(f"Competitive-edge relevance: {diff[0].headline} These terms should be watched because they can become the next investor differentiation framework.")
    if side:
        brief.append(f"Side-channel relevance: {side[0].headline} This should remain separate from the core oncology read, but it can support partnering or grant strategy.")
    if theme_table is not None and not theme_table.empty:
        top_theme = str(theme_table.iloc[0]["Theme"])
        brief.append(f"Theme concentration: {top_theme} is currently the strongest repeated relevance marker across the signal set.")
    return brief[:5]
