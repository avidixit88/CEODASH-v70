"""Curated catalyst dataset for Iteration 5.

Important CTO note:
Manual curation is only a v1 bridge. We should not rely on manual updating once
leadership begins using the dashboard regularly. This file defines the canonical
schema that future ingestion jobs should populate from IR feeds, press releases,
conference abstract pages, SEC filings, ClinicalTrials.gov, and licensed news APIs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalystEvent:
    ticker: str
    company: str
    title: str
    category: str
    expected_timing: str
    asset: str
    target: str
    indication: str
    impact: str
    read_through: str
    status: str
    source_note: str
    source_url: str = ""


CATALYST_EVENTS: tuple[CatalystEvent, ...] = (
    CatalystEvent(
        ticker="NXTC",
        company="NextCure",
        title="SIM0505 Phase 1 data presentation at ASCO 2026",
        category="Clinical data",
        expected_timing="ASCO 2026",
        asset="SIM0505",
        target="CDH6",
        indication="Advanced solid tumors, emphasis on platinum-resistant ovarian cancer",
        impact="High",
        read_through="Primary",
        status="Upcoming",
        source_note="NextCure announced ASCO acceptance and FDA Fast Track designation for SIM0505 in PROC.",
        source_url="https://ir.nextcure.com/news-releases/news-release-details/nextcure-and-simceres-sim0505-cdh6-adc-phase-1-data-be-presented",
    ),
    CatalystEvent(
        ticker="NXTC",
        company="NextCure",
        title="SIM0505 ovarian cancer dose optimization expected to begin",
        category="Clinical development",
        expected_timing="Q2 2026",
        asset="SIM0505",
        target="CDH6",
        indication="Platinum-resistant ovarian cancer",
        impact="High",
        read_through="Primary",
        status="Upcoming",
        source_note="Fast Track release states dose optimization in ovarian cancer expected in Q2 2026.",
        source_url="https://ir.nextcure.com/news-releases/news-release-details/nextcure-receives-fast-track-designation-sim0505-cdh6-adc-0/",
    ),
    CatalystEvent(
        ticker="GSK",
        company="GSK",
        title="Mo-rez / mocertatug rezetecan B7-H4 ADC late-stage expansion",
        category="Clinical development",
        expected_timing="2026",
        asset="Mocertatug rezetecan",
        target="B7-H4",
        indication="Platinum-resistant ovarian and endometrial cancers",
        impact="High",
        read_through="High",
        status="Active",
        source_note="GSK reported strong gynecologic cancer activity and late-stage study plans.",
        source_url="https://www.gsk.com/en-gb/media/press-releases/gsk-presents-positive-data-for-b7-h4-targeted-adc-in-gynaecological-cancers/",
    ),
    CatalystEvent(
        ticker="MRK",
        company="Merck / Daiichi Sankyo",
        title="Raludotatug deruxtecan CDH6 ADC regulatory and clinical momentum",
        category="Regulatory / Clinical",
        expected_timing="Ongoing",
        asset="Raludotatug deruxtecan",
        target="CDH6",
        indication="CDH6-expressing platinum-resistant ovarian / peritoneal / fallopian tube cancers",
        impact="High",
        read_through="High",
        status="Active",
        source_note="FDA Breakthrough Therapy designation provides strong read-through for the CDH6 lane.",
        source_url="https://www.merck.com/news/raludotatug-deruxtecan-granted-breakthrough-therapy-designation-by-u-s-fda-for-patients-with-cdh6-expressing-platinum-resistant-ovarian-primary-peritoneal-or-fallopian-tube-cancers-previously-treat/",
    ),
    CatalystEvent(
        ticker="DSNKY",
        company="Daiichi Sankyo",
        title="ADC portfolio read-through across DXd platform",
        category="Modality read-through",
        expected_timing="Ongoing",
        asset="DXd ADC portfolio",
        target="HER2 / TROP2 / HER3 / B7-H3 / CDH6",
        indication="Multiple solid tumors",
        impact="Medium",
        read_through="Medium-High",
        status="Active",
        source_note="Platform-level read-through matters for broad ADC capital appetite.",
    ),
    CatalystEvent(
        ticker="ZYME",
        company="Zymeworks",
        title="FRα / NaPi2b ADC updates as ovarian cancer modality read-through",
        category="Pipeline read-through",
        expected_timing="Ongoing",
        asset="ZW191 / ZW220",
        target="FRα / NaPi2b",
        indication="Ovarian, endometrial, lung, pancreatic cancers",
        impact="Medium",
        read_through="Medium",
        status="Active",
        source_note="Useful comparator for ovarian ADC investor appetite outside CDH6/B7-H4.",
    ),
    CatalystEvent(
        ticker="NXTC",
        company="NextCure",
        title="NC181 Alzheimer’s partnering lane",
        category="Partnering",
        expected_timing="Future / partnering dependent",
        asset="NC181",
        target="ApoE4-related biology",
        indication="Alzheimer’s disease",
        impact="Medium",
        read_through="Separate channel",
        status="Watch",
        source_note="Kept separate from oncology so capital-flow interpretation remains clean.",
    ),
    CatalystEvent(
        ticker="NXTC",
        company="NextCure",
        title="NC605 bone disease / Siglec-15 partnering lane",
        category="Partnering",
        expected_timing="Future / funding dependent",
        asset="NC605",
        target="Siglec-15",
        indication="Osteogenesis imperfecta / chronic bone disease",
        impact="Medium",
        read_through="Separate channel",
        status="Watch",
        source_note="Side-channel asset, not blended into ovarian/ADC market interpretation.",
    ),
)


def future_ingestion_backlog() -> list[dict[str, str]]:
    """Return future backend ingestion tasks without exposing them as user toggles."""
    return [
        {
            "source": "Company IR press-release RSS / HTML pages",
            "purpose": "Detect new company catalysts, trial updates, financings, and data presentations.",
            "status": "Hook scaffolded; parser not active in v0.5.",
        },
        {
            "source": "ClinicalTrials.gov",
            "purpose": "Track trial status, enrollment, dose expansion, endpoints, and study updates.",
            "status": "Hook scaffolded; parser not active in v0.5.",
        },
        {
            "source": "Conference abstract pages",
            "purpose": "Capture ASCO/AACR/ESMO/SITC abstract releases and presentation timing.",
            "status": "Hook scaffolded; parser not active in v0.5.",
        },
        {
            "source": "SEC filings and financings",
            "purpose": "Connect market moves to financing windows, ATM usage, cash runway, and investor appetite.",
            "status": "Hook scaffolded; parser not active in v0.5.",
        },
    ]
