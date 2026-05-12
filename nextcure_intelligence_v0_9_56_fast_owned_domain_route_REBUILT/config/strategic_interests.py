"""NextCure-specific strategic interest profile.

This file is intentionally separate from peer/catalyst configuration. It models
NextCure's strategic priorities, so incoming items can be scored for relevance before
being synthesized into executive intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategicInterestProfile:
    company: str
    primary_targets: tuple[str, ...]
    secondary_targets: tuple[str, ...]
    modalities: tuple[str, ...]
    primary_indications: tuple[str, ...]
    side_channels: tuple[str, ...]
    value_drivers: tuple[str, ...]
    watch_terms: tuple[str, ...]


NEXTCURE_PROFILE = StrategicInterestProfile(
    company="NextCure",
    primary_targets=("CDH6", "B7-H4"),
    secondary_targets=("Siglec-15", "ApoE4", "NC181", "NC605"),
    modalities=("ADC", "antibody-drug conjugate", "immuno-oncology", "targeted oncology"),
    primary_indications=("platinum-resistant ovarian cancer", "ovarian cancer", "advanced solid tumors"),
    side_channels=("Alzheimer's", "bone disease", "osteogenesis imperfecta", "rare bone disease"),
    value_drivers=(
        "payload differentiation",
        "linker innovation",
        "toxicity reduction",
        "patient selection",
        "biomarker strategy",
        "partnering",
        "non-dilutive funding",
        "clinical validation",
    ),
    watch_terms=(
        "CDH6",
        "B7-H4",
        "ADC",
        "ovarian",
        "platinum-resistant",
        "Siglec-15",
        "ApoE4",
        "Alzheimer",
        "bone disease",
        "osteogenesis imperfecta",
        "payload",
        "linker",
        "toxicity",
        "grant",
        "patent",
        "SBIR",
        "NIH",
        "abstract",
    ),
)


# v0.9.2 uses a curated seed list as a safe bridge. Future ingestion jobs should
# populate the same fields from patents, NIH/RePORTER, conference abstracts,
# press releases, ClinicalTrials.gov, SEC filings, and approved news sources.
CURATED_SIGNAL_SEEDS: tuple[dict[str, str], ...] = (
    {
        "source_type": "Catalyst / competitive read-through",
        "headline": "CDH6 ADC activity remains the primary market read-through lane for SIM0505.",
        "entities": "CDH6, ADC, ovarian cancer, platinum-resistant disease",
        "why_relevant": "Directly overlaps with SIM0505 positioning and can influence how investors benchmark NextCure's catalyst.",
        "strategic_question": "Are investors treating CDH6 as a validated ovarian ADC lane, and is NXTC receiving credit for that validation?",
        "recommended_next_source": "Track competitor updates, conference abstracts, regulatory milestones, and CDH6-related patent filings.",
    },
    {
        "source_type": "Adjacent ADC lane",
        "headline": "B7-H4 ADC data and late-stage movement may shape ovarian/gynecologic ADC investor expectations.",
        "entities": "B7-H4, ADC, gynecologic cancer, ovarian cancer",
        "why_relevant": "Not identical to CDH6, but it competes for the same investor attention bucket around ovarian ADC opportunity.",
        "strategic_question": "Is the market rewarding ovarian ADC modality momentum broadly, or only specific target/company narratives?",
        "recommended_next_source": "Monitor B7-H4 abstracts, partner commentary, patent claims, and financing behavior around gynecologic ADC companies.",
    },
    {
        "source_type": "Side-channel / partnering",
        "headline": "Alzheimer's and bone-disease programs should be monitored as separate optionality lanes, not blended into oncology valuation.",
        "entities": "ApoE4, Alzheimer's, Siglec-15, bone disease, osteogenesis imperfecta",
        "why_relevant": "These side channels may create partnering or non-dilutive funding opportunities, but they should not confuse the core SIM0505 market read.",
        "strategic_question": "Are grants, patents, or academic collaborations creating external validation for side-channel assets?",
        "recommended_next_source": "Track NIH grants, foundation grants, academic publications, patent filings, and partner activity around ApoE4/Siglec-15 biology.",
    },
    {
        "source_type": "Technology trend",
        "headline": "Payload, linker, toxicity, and patient-selection language should be treated as competitive-edge indicators inside ADC intelligence.",
        "entities": "payload, linker, toxicity, biomarker, patient selection, resistance",
        "why_relevant": "ADC differentiation is increasingly narrative-driven. The system should identify whether competitors are claiming advantages NXTC may need to counter or align with.",
        "strategic_question": "What scientific differentiation theme is becoming more important to investors before it appears in stock behavior?",
        "recommended_next_source": "Parse patent abstracts/claims, poster language, company decks, and grant abstracts for repeated differentiation claims.",
    },
)
