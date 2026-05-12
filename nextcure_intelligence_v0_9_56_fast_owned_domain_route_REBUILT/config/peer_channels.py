"""Curated peer and landscape configuration for the NextCure Intelligence System.

This file is intentionally data/config only. The UI and engines consume these
records without hardcoding peer lists into Streamlit pages.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PeerCompany:
    ticker: str
    company: str
    channels: tuple[str, ...]
    targets: tuple[str, ...]
    indications: tuple[str, ...]
    read_through: str
    priority: str = "medium"
    status: str = "active"
    notes: str = ""


BENCHMARK_TICKERS: tuple[str, ...] = ("NXTC", "XBI", "QQQ")

# v0.3 deliberately separates direct read-through peers from broad ADC/capital-flow names.
# Large-cap tickers are included because their ADC updates often influence category sentiment.
PEER_COMPANIES: tuple[PeerCompany, ...] = (
    PeerCompany(
        ticker="NXTC",
        company="NextCure",
        channels=("primary", "cdh6_ovarian_adc", "b7h4_adc", "ovarian_cancer", "adc_capital_flow"),
        targets=("CDH6", "B7-H4"),
        indications=("Platinum-resistant ovarian cancer", "Gynecologic cancers"),
        read_through="Primary company",
        priority="highest",
    ),
    PeerCompany(
        ticker="MRK",
        company="Merck",
        channels=("cdh6_ovarian_adc", "ovarian_cancer", "adc_capital_flow"),
        targets=("CDH6", "B7-H3"),
        indications=("Ovarian cancer", "Small-cell lung cancer"),
        read_through="High",
        priority="high",
    ),
    PeerCompany(
        ticker="DSNKY",
        company="Daiichi Sankyo",
        channels=("cdh6_ovarian_adc", "adc_capital_flow"),
        targets=("CDH6", "HER2", "TROP2", "HER3", "B7-H3"),
        indications=("Ovarian cancer", "Breast cancer", "Lung cancer"),
        read_through="High",
        priority="high",
    ),
    PeerCompany(
        ticker="GSK",
        company="GSK",
        channels=("b7h4_adc", "ovarian_cancer", "adc_capital_flow"),
        targets=("B7-H4",),
        indications=("Ovarian cancer", "Endometrial cancer", "Gynecologic cancers"),
        read_through="High",
        priority="high",
    ),
    PeerCompany(
        ticker="AZN",
        company="AstraZeneca",
        channels=("b7h4_adc", "adc_capital_flow"),
        targets=("HER2", "TROP2", "B7-H4"),
        indications=("Breast cancer", "Lung cancer", "Gynecologic cancers"),
        read_through="Medium-High",
        priority="high",
    ),
    PeerCompany(
        ticker="GILD",
        company="Gilead",
        channels=("ovarian_cancer", "adc_capital_flow"),
        targets=("TROP2", "NaPi2b"),
        indications=("Breast cancer", "Ovarian cancer", "Lung cancer"),
        read_through="Medium-High",
        priority="high",
    ),
    PeerCompany(
        ticker="GMAB",
        company="Genmab",
        channels=("ovarian_cancer", "adc_capital_flow"),
        targets=("FRα",),
        indications=("Ovarian cancer",),
        read_through="Medium-High",
        priority="high",
    ),
    PeerCompany(
        ticker="ABBV",
        company="AbbVie",
        channels=("ovarian_cancer", "adc_capital_flow"),
        targets=("FRα", "c-Met", "SEZ6"),
        indications=("Ovarian cancer", "Solid tumors"),
        read_through="Medium",
        priority="medium",
    ),
    PeerCompany(
        ticker="ZYME",
        company="Zymeworks",
        channels=("ovarian_cancer", "adc_capital_flow", "small_cap_oncology"),
        targets=("FRα", "NaPi2b", "PTK7"),
        indications=("Ovarian cancer", "Endometrial cancer", "Lung cancer", "Pancreatic cancer"),
        read_through="Medium-High",
        priority="high",
    ),
    PeerCompany(
        ticker="DAWN",
        company="Day One Biopharmaceuticals",
        channels=("b7h4_adc", "adc_capital_flow", "small_cap_oncology"),
        targets=("B7-H4", "PTK7"),
        indications=("Solid tumors",),
        read_through="Medium",
        priority="medium",
    ),
    PeerCompany(
        ticker="ADCT",
        company="ADC Therapeutics",
        channels=("adc_capital_flow", "small_cap_oncology"),
        targets=("CD19", "DLK1"),
        indications=("Lymphoma", "Solid tumors"),
        read_through="Low-Medium",
        priority="medium",
    ),
    PeerCompany(
        ticker="IOVA",
        company="Iovance Biotherapeutics",
        channels=("small_cap_oncology",),
        targets=("Cell therapy",),
        indications=("Melanoma", "Solid tumors"),
        read_through="Low-Medium",
        priority="medium",
    ),
    PeerCompany(
        ticker="FATE",
        company="Fate Therapeutics",
        channels=("small_cap_oncology",),
        targets=("Cell therapy",),
        indications=("Oncology", "Autoimmune"),
        read_through="Low",
        priority="low",
    ),
    PeerCompany(
        ticker="ADAP",
        company="Adaptimmune Therapeutics",
        channels=("small_cap_oncology",),
        targets=("TCR therapy",),
        indications=("Solid tumors",),
        read_through="Low",
        priority="low",
    ),
    PeerCompany(
        ticker="BIIB",
        company="Biogen",
        channels=("alzheimers_partnering_channel",),
        targets=("Amyloid", "Tau", "Neurodegeneration"),
        indications=("Alzheimer's disease",),
        read_through="Side-channel",
        priority="medium",
    ),
    PeerCompany(
        ticker="LLY",
        company="Eli Lilly",
        channels=("alzheimers_partnering_channel",),
        targets=("Amyloid", "Neurodegeneration"),
        indications=("Alzheimer's disease",),
        read_through="Side-channel",
        priority="medium",
    ),
    PeerCompany(
        ticker="ESAIY",
        company="Eisai",
        channels=("alzheimers_partnering_channel",),
        targets=("Amyloid",),
        indications=("Alzheimer's disease",),
        read_through="Side-channel",
        priority="medium",
    ),
    PeerCompany(
        ticker="AMGN",
        company="Amgen",
        channels=("bone_disease_partnering_channel",),
        targets=("Bone biology", "Oncology"),
        indications=("Bone disease", "Oncology"),
        read_through="Side-channel",
        priority="medium",
    ),
    PeerCompany(
        ticker="RARE",
        company="Ultragenyx",
        channels=("bone_disease_partnering_channel",),
        targets=("Rare disease", "Bone disease"),
        indications=("Rare bone disease",),
        read_through="Side-channel",
        priority="medium",
    ),
)


def all_market_tickers() -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for ticker in BENCHMARK_TICKERS + tuple(company.ticker for company in PEER_COMPANIES):
        if ticker not in seen:
            seen.add(ticker)
            ordered.append(ticker)
    return ordered


def peer_metadata_by_ticker() -> dict[str, PeerCompany]:
    return {company.ticker: company for company in PEER_COMPANIES}


def companies_for_channel(channel: str) -> list[PeerCompany]:
    return [company for company in PEER_COMPANIES if channel in company.channels]
