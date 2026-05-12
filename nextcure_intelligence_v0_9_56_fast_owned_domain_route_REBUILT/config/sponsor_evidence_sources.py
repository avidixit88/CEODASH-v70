"""Sponsor evidence-source configuration.

This file intentionally separates trial sponsors from evidence-search handles.
ClinicalTrials.gov tells us who is running trials; this map tells the prototype
how to look for recent sponsor communications without hardcoding executive
answers. Later this can be replaced by a database table or richer source router.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SponsorEvidenceSource:
    sponsor: str
    tickers: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    priority: int = 50
    evidence_terms: tuple[str, ...] = ()


SPONSOR_EVIDENCE_LOOKUP: tuple[SponsorEvidenceSource, ...] = (
    SponsorEvidenceSource("NextCure", ("NXTC",), ("NextCure, Inc.", "SIM0505"), 0, ("sim0505", "cdh6", "ovarian", "platinum-resistant", "proc", "adc", "asco", "dose optimization", "phase 1")),
    SponsorEvidenceSource("Daiichi Sankyo", ("4568.T",), ("Daiichi", "datopotamab", "DS-6000", "raludotatug"), 1, ("cdh6", "ds-6000", "raludotatug", "datopotamab", "ovarian", "adc")),
    SponsorEvidenceSource("AstraZeneca", ("AZN",), ("AstraZeneca PLC", "AZ"), 2, ("b7-h4", "b7h4", "ovarian", "gynecologic", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("Genmab", ("GMAB",), ("Genmab A/S",), 3, ("ovarian", "b7-h4", "b7h4", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("Bristol-Myers Squibb", ("BMY",), ("BMS", "Bristol Myers"), 4, ("ovarian", "gynecologic", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("Novartis Pharmaceuticals", ("NVS",), ("Novartis",), 5, ("cdh6", "ovarian", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("Eli Lilly and Company", ("LLY",), ("Eli Lilly", "Lilly"), 6, ("ovarian", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("BioNTech SE", ("BNTX",), ("BioNTech",), 7, ("ovarian", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("Merck Sharp & Dohme LLC", ("MRK",), ("Merck", "MSD"), 8, ("adc", "antibody-drug conjugate", "ovarian", "gynecologic")),
    SponsorEvidenceSource("Pfizer", ("PFE",), ("Pfizer Inc",), 9, ("b7-h4", "b7h4", "ovarian", "adc", "antibody-drug conjugate")),
    SponsorEvidenceSource("BeOne Medicines", ("ONC", "BGNE"), ("BeiGene", "BeOne"), 10, ("b7-h4", "b7h4", "ovarian", "gynecologic", "adc", "antibody-drug conjugate")),
)


MAX_SPONSORS_PER_RUN = 20
MAX_NEWS_ITEMS_PER_TICKER = 20
