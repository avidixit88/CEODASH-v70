"""Dynamic sponsor discovery from ClinicalTrials.gov records.

The discovery registry is intentionally built from the records returned by the
live ClinicalTrials.gov pull. Static sponsor/ticker maps can enrich an entity,
but they are never allowed to decide who exists in the battlefield.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Protocol
from urllib.parse import quote_plus

import pandas as pd


class TrialLike(Protocol):
    nct_id: str
    title: str
    sponsor: str
    collaborators: str
    lane: str
    phase: str
    status: str
    interventions: str
    conditions: str
    last_update: str
    sponsor_type: str


LEGAL_SUFFIX_RE = re.compile(
    r"\b(incorporated|inc\.?|llc|l\.l\.c\.?|ltd\.?|limited|co\.?|company|corp\.?|corporation|plc|ag|sa|s\.a\.?|se|gmbh|bv|b\.v\.?|kk|k\.k\.?|pte\.?|holdings?|pharmaceuticals?|pharma|therapeutics)\b",
    re.IGNORECASE,
)
PUNCT_RE = re.compile(r"[^a-z0-9&+ ]+")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class DiscoveredSponsor:
    sponsor_name: str
    normalized_name: str
    aliases: tuple[str, ...]
    roles: tuple[str, ...]
    matched_lanes: tuple[str, ...]
    nct_ids: tuple[str, ...]
    trial_count: int
    phases: tuple[str, ...]
    statuses: tuple[str, ...]
    program_terms: tuple[str, ...]
    conditions: tuple[str, ...]
    sponsor_type: str
    last_update: str
    relevance_score: int
    evidence_queries: tuple[str, ...]


def normalize_sponsor_name(name: str) -> str:
    """Collapse obvious subsidiary/legal variants while keeping readable names."""
    raw = (name or "").strip()
    if not raw:
        return "Unknown sponsor"
    text = raw.replace("&", " and ")
    # Remove country/location parentheticals that create duplicate subsidiaries.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = LEGAL_SUFFIX_RE.sub(" ", text)
    text = PUNCT_RE.sub(" ", text.lower())
    text = SPACE_RE.sub(" ", text).strip()
    corrections = {
        "daiichi sankyo": "Daiichi Sankyo",
        "bristol myers squibb": "Bristol Myers Squibb",
        "bristol myers": "Bristol Myers Squibb",
        "astrazeneca": "AstraZeneca",
        "eli lilly": "Eli Lilly",
        "merck sharp dohme": "Merck Sharp & Dohme",
        "msd": "Merck Sharp & Dohme",
        "beigene": "BeiGene / BeOne Medicines",
        "beone medicines": "BeiGene / BeOne Medicines",
    }
    if text in corrections:
        return corrections[text]
    return " ".join(part.capitalize() if len(part) > 2 else part.upper() for part in text.split()) or raw


def _split_names(value: str) -> list[str]:
    if not value or value in {"None listed", "Unknown sponsor"}:
        return []
    return [part.strip() for part in value.split(",") if part.strip() and part.strip() != "None listed"]


def _unique(values: Iterable[str], limit: int | None = None) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        value = str(value or "").strip()
        if value and value not in out and value not in {"Not specified", "None listed"}:
            out.append(value)
        if limit and len(out) >= limit:
            break
    return tuple(out)


def _program_terms(text: str) -> tuple[str, ...]:
    terms = [
        "CDH6", "cadherin 6", "DS-6000", "DS-6000a", "raludotatug", "R-DXd",
        "B7-H4", "B7H4", "VTCN1", "SIM0505", "SIM0505-101", "ADC", "antibody-drug conjugate",
        "folate receptor", "FR alpha", "FRα", "TROP2", "HER2", "NaPi2b",
    ]
    haystack = text.lower()
    return tuple(dict.fromkeys(t for t in terms if t.lower() in haystack))


def _evidence_queries(name: str, program_terms: Iterable[str], lanes: Iterable[str]) -> tuple[str, ...]:
    core_terms = " OR ".join(dict.fromkeys(program_terms)) or "ADC OR ovarian OR gynecologic"
    lane_terms = " OR ".join(dict.fromkeys(lanes)) or "oncology"
    sponsor = quote_plus(name)
    query_text = quote_plus(f'"{name}" ({core_terms}) (ORR OR PFS OR DOR OR safety OR data OR ASCO OR AACR OR ESMO OR SITC OR press release OR investor relations)')
    return (
        f"https://www.google.com/search?q={query_text}",
        f"https://www.businesswire.com/portal/site/home/search/?searchType=news&searchTerm={sponsor}",
        f"https://www.globenewswire.com/search/keyword/{sponsor}",
        f"https://www.prnewswire.com/search/news/?keyword={sponsor}",
        f"https://www.google.com/search?q={quote_plus(name + ' investor relations press release ' + lane_terms)}",
    )


def build_discovered_sponsor_registry(records: list[TrialLike]) -> list[DiscoveredSponsor]:
    registry: dict[str, dict[str, object]] = {}

    for r in records:
        entities: list[tuple[str, str]] = []
        if getattr(r, "sponsor", "") and r.sponsor != "Unknown sponsor":
            entities.append((r.sponsor, "lead sponsor"))
        entities.extend((name, "collaborator") for name in _split_names(getattr(r, "collaborators", "")))

        for raw_name, role in entities:
            normalized = normalize_sponsor_name(raw_name)
            entry = registry.setdefault(normalized, {
                "aliases": [], "roles": [], "lanes": [], "nct_ids": [], "phases": [], "statuses": [],
                "program_terms": [], "conditions": [], "types": [], "last_update": "", "titles": [],
            })
            for key, value in [
                ("aliases", raw_name), ("roles", role), ("lanes", r.lane), ("nct_ids", r.nct_id),
                ("phases", r.phase), ("statuses", r.status), ("conditions", r.conditions),
                ("types", r.sponsor_type), ("titles", r.title),
            ]:
                values = entry[key]  # type: ignore[index]
                if value and value not in values:  # type: ignore[operator]
                    values.append(value)  # type: ignore[union-attr]
            haystack = " ".join([r.title, r.interventions, r.conditions, r.lane])
            for term in _program_terms(haystack):
                terms = entry["program_terms"]  # type: ignore[index]
                if term not in terms:  # type: ignore[operator]
                    terms.append(term)  # type: ignore[union-attr]
            if str(r.last_update or "") > str(entry.get("last_update") or ""):
                entry["last_update"] = r.last_update

    sponsors: list[DiscoveredSponsor] = []
    direct_lanes = {"CDH6 / Ovarian ADC", "B7-H4 ADC", "Ovarian ADC", "ADC Oncology"}
    for normalized, entry in registry.items():
        aliases = _unique(entry["aliases"])  # type: ignore[arg-type]
        lanes = _unique(entry["lanes"])  # type: ignore[arg-type]
        nct_ids = _unique(entry["nct_ids"])  # type: ignore[arg-type]
        phases = _unique(entry["phases"])  # type: ignore[arg-type]
        roles = _unique(entry["roles"])  # type: ignore[arg-type]
        programs = _unique(entry["program_terms"], limit=8)  # type: ignore[arg-type]
        conditions = _unique(entry["conditions"], limit=5)  # type: ignore[arg-type]
        types = _unique(entry["types"], limit=2)  # type: ignore[arg-type]
        score = len(nct_ids) * 2
        score += 6 if any(lane in direct_lanes for lane in lanes) else 0
        score += 4 if any("PHASE3" in p.upper().replace(" ", "") for p in phases) else 0
        score += 2 if any("PHASE2" in p.upper().replace(" ", "") for p in phases) else 0
        score += 2 if programs else 0
        score += 1 if "lead sponsor" in roles else 0
        sponsors.append(DiscoveredSponsor(
            sponsor_name=normalized,
            normalized_name=normalized,
            aliases=aliases,
            roles=roles,
            matched_lanes=lanes,
            nct_ids=nct_ids,
            trial_count=len(nct_ids),
            phases=phases,
            statuses=_unique(entry["statuses"], limit=5),  # type: ignore[arg-type]
            program_terms=programs,
            conditions=conditions,
            sponsor_type=types[0] if types else "Other sponsor",
            last_update=str(entry.get("last_update") or ""),
            relevance_score=score,
            evidence_queries=_evidence_queries(normalized, programs, lanes),
        ))

    return sorted(sponsors, key=lambda s: (s.relevance_score, s.last_update, s.trial_count), reverse=True)


def sponsor_discovery_table(sponsors: list[DiscoveredSponsor]) -> pd.DataFrame:
    columns = [
        "Sponsor", "Roles", "Matched Lanes", "Trial Count", "NCT IDs", "Phases",
        "Programs / Terms", "Sponsor Type", "Last Update", "Relevance Score", "Evidence Search Links",
    ]
    if not sponsors:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([
        {
            "Sponsor": s.sponsor_name,
            "Roles": ", ".join(s.roles),
            "Matched Lanes": ", ".join(s.matched_lanes),
            "Trial Count": s.trial_count,
            "NCT IDs": ", ".join(s.nct_ids[:8]),
            "Phases": ", ".join(s.phases),
            "Programs / Terms": ", ".join(s.program_terms),
            "Sponsor Type": s.sponsor_type,
            "Last Update": s.last_update,
            "Relevance Score": s.relevance_score,
            "Evidence Search Links": " | ".join(s.evidence_queries[:3]),
        }
        for s in sponsors
    ])
