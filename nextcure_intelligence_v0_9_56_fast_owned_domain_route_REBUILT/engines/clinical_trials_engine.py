"""Live ClinicalTrials.gov intelligence lane.

Phase 1 goal:
- Pull compact live trial signals from ClinicalTrials.gov on each analysis run.
- Score and synthesize them into the four executive buckets.
- Preserve backend hooks so the same structured study records can later be persisted
  into a database without changing the executive UI contract.

This module intentionally avoids a Streamlit cache. While the prototype is on
Streamlit Community Cloud, each run fetches fresh data with small page sizes and
short timeouts, then fails gracefully if the upstream service is unavailable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import json
from typing import Any

from engines.sponsor_evidence_engine import SponsorEvidenceSummary, build_sponsor_evidence_summary, sponsor_evidence_table
from engines.sponsor_discovery_engine import DiscoveredSponsor, build_discovered_sponsor_registry, sponsor_discovery_table
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from config.clinical_trials_sources import (
    CLINICAL_TRIALS_MAX_PAGES_PER_SPEC,
    CLINICAL_TRIALS_PAGE_SIZE,
    CLINICAL_TRIALS_TIMEOUT_SECONDS,
    CLINICAL_TRIAL_SEARCH_SPECS,
    ClinicalTrialSearchSpec,
)

API_BASE = "https://clinicaltrials.gov/api/v2/studies"


DIRECT_LANE_ORDER = ["CDH6 / Ovarian ADC", "B7-H4 ADC", "Ovarian ADC"]
SIDE_LANE_ORDER = ["Alzheimer's Side Channel", "Bone Disease Side Channel"]
LANE_DISPLAY = {
    "CDH6 / Ovarian ADC": "CDH6 / ovarian ADC",
    "B7-H4 ADC": "B7-H4 ADC",
    "Ovarian ADC": "ovarian ADC",
    "ADC Oncology": "broader oncology ADC",
    "Alzheimer's Side Channel": "Alzheimer's exploratory area",
    "Bone Disease Side Channel": "bone-disease exploratory area",
}


def _lane_label(lane: str) -> str:
    return LANE_DISPLAY.get(lane, lane.replace(" Side Channel", " exploratory area"))


def _join_labels(lanes: list[str]) -> str:
    labels = [_lane_label(lane) for lane in lanes]
    if not labels:
        return "the monitored clinical landscape"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


@dataclass(frozen=True)
class TrialRecord:
    nct_id: str
    title: str
    sponsor: str
    phase: str
    status: str
    conditions: str
    interventions: str
    start_date: str
    last_update: str
    source_query: str
    lane: str
    url: str
    enrollment: str
    primary_outcomes: str
    secondary_outcomes: str
    observed_results: str
    eligibility_criteria: str
    countries: str
    collaborators: str
    sponsor_type: str
    query_family: str = "unknown"
    query_area: str = "term"
    fetched_pages: int = 0
    available_total: int | None = None
    discovery_queries: tuple[str, ...] = ()
    matched_fields: tuple[str, ...] = ()
    relevance_score: int = 0


@dataclass(frozen=True)
class ClinicalTrialSignal:
    bucket: str
    title: str
    finding: str
    value: str
    evidence: str
    priority: int


@dataclass(frozen=True)
class ClinicalTrialsDiscoveryAudit:
    label: str
    query_family: str
    query_area: str
    query: str
    fetched_pages: int
    fetched_records: int
    retained_records: int
    available_total: int | None
    truncated: bool
    error: str = ""


@dataclass(frozen=True)
class ClinicalTrialsSummary:
    source_status: str
    fetched_at_utc: str
    total_trials: int
    active_trials: int
    lanes_covered: list[str]
    signals: list[ClinicalTrialSignal]
    trial_table: pd.DataFrame
    persistence_payload: list[dict[str, Any]]
    source_errors: list[str]
    sponsor_evidence: SponsorEvidenceSummary | None = None
    discovered_sponsors: list[DiscoveredSponsor] | None = None
    sponsor_discovery_table: pd.DataFrame | None = None
    discovery_audit: list[ClinicalTrialsDiscoveryAudit] | None = None
    discovery_audit_table: pd.DataFrame | None = None

    @property
    def new_information(self) -> list[str]:
        return [s.finding for s in self.signals if s.bucket == "new_information"]

    @property
    def value_interpretation(self) -> list[str]:
        return [s.value for s in self.signals if s.bucket == "value"]

    @property
    def trend_inference(self) -> list[str]:
        return [s.finding for s in self.signals if s.bucket == "trend"]

    @property
    def positioning_implications(self) -> list[str]:
        return [s.finding for s in self.signals if s.bucket == "positioning"]


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(_extract_text(v) for v in value if _extract_text(v))
    if isinstance(value, dict):
        return ", ".join(_extract_text(v) for v in value.values() if _extract_text(v))
    return str(value).strip()


def _first_date(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("date") or value.get("startDate") or value.get("completionDate") or "")
    return _extract_text(value)


def _phase(protocol: dict[str, Any]) -> str:
    phases = protocol.get("designModule", {}).get("phases")
    text = _extract_text(phases)
    return text or "Not specified"


def _sponsor(protocol: dict[str, Any]) -> str:
    lead = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
    return _extract_text(lead.get("name")) or "Unknown sponsor"


def _interventions(protocol: dict[str, Any]) -> str:
    arms = protocol.get("armsInterventionsModule", {}).get("interventions", []) or []
    names = []
    for item in arms:
        name = item.get("name") if isinstance(item, dict) else None
        if name:
            names.append(str(name))
    return ", ".join(dict.fromkeys(names)) or "Not specified"


def _conditions(protocol: dict[str, Any]) -> str:
    return _extract_text(protocol.get("conditionsModule", {}).get("conditions")) or "Not specified"


def _status(protocol: dict[str, Any]) -> str:
    return _extract_text(protocol.get("statusModule", {}).get("overallStatus")) or "Unknown"


def _title(protocol: dict[str, Any]) -> str:
    id_module = protocol.get("identificationModule", {})
    return _extract_text(id_module.get("briefTitle") or id_module.get("officialTitle")) or "Untitled trial"


def _nct_id(protocol: dict[str, Any]) -> str:
    return _extract_text(protocol.get("identificationModule", {}).get("nctId"))


def _enrollment(protocol: dict[str, Any]) -> str:
    enrollment = protocol.get("designModule", {}).get("enrollmentInfo", {})
    count = enrollment.get("count") if isinstance(enrollment, dict) else None
    if count in (None, ""):
        return "Not specified"
    return str(count)


def _outcomes(protocol: dict[str, Any], key: str) -> str:
    outcomes = protocol.get("outcomesModule", {}).get(key, []) or []
    parts: list[str] = []
    for item in outcomes:
        if not isinstance(item, dict):
            continue
        measure = _extract_text(item.get("measure"))
        description = _extract_text(item.get("description"))
        if measure and description:
            parts.append(f"{measure}: {description}")
        elif measure:
            parts.append(measure)
        elif description:
            parts.append(description)
    return "; ".join(dict.fromkeys(parts)) or "Not specified"


def _result_measure_title(measure: dict[str, Any]) -> str:
    return _extract_text(
        measure.get("title")
        or measure.get("measure")
        or measure.get("name")
        or measure.get("description")
    )


def _iter_result_measurements(node: Any) -> list[dict[str, Any]]:
    """Return ClinicalTrials.gov result measurement leaves from a loose schema.

    The v2 API can nest posted results under classes/categories/measurements.
    We intentionally parse defensively so future upstream schema shifts do not
    break the dashboard.
    """
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if any(k in node for k in ("value", "upperLimit", "lowerLimit")):
            found.append(node)
        for value in node.values():
            found.extend(_iter_result_measurements(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_iter_result_measurements(item))
    return found


def _observed_results(study: dict[str, Any]) -> str:
    """Extract posted/observed outcome values when ClinicalTrials.gov provides them.

    Many active trials expose endpoint *plans* but not posted result values.
    This field lets the intelligence layer separate protocol burden from actual
    efficacy/tolerability readout evidence without inventing numbers.
    """
    results = study.get("resultsSection", {}) if isinstance(study, dict) else {}
    measures = (
        results.get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
        if isinstance(results, dict) else []
    ) or []
    parts: list[str] = []
    for measure in measures:
        if not isinstance(measure, dict):
            continue
        title = _result_measure_title(measure)
        if not title:
            continue
        title_l = title.lower()
        # Prioritize values that executives/investors usually ask about first.
        if not any(token in title_l for token in [
            "response", "orr", "progression", "pfs", "duration", "dor",
            "survival", "safety", "tolerability", "adverse", "toxicity",
            "dose", "disease control", "complete response", "partial response",
        ]):
            continue
        units = _extract_text(measure.get("unitOfMeasure") or measure.get("units"))
        param = _extract_text(measure.get("paramType"))
        values: list[str] = []
        for m in _iter_result_measurements(measure):
            raw_val = _extract_text(m.get("value"))
            if not raw_val or raw_val.lower() in {"na", "n/a", "not applicable"}:
                continue
            unit = _extract_text(m.get("unitOfMeasure") or m.get("units")) or units
            suffix = f" {unit}" if unit and unit not in raw_val else ""
            val = f"{raw_val}{suffix}"
            if val not in values:
                values.append(val)
            if len(values) >= 3:
                break
        if values:
            label = title[:80].strip()
            method = f" ({param})" if param else ""
            parts.append(f"{label}{method}: {', '.join(values)}")
        if len(parts) >= 5:
            break
    return "; ".join(parts) or "No posted result values surfaced"


def _eligibility_criteria(protocol: dict[str, Any]) -> str:
    text = _extract_text(protocol.get("eligibilityModule", {}).get("eligibilityCriteria"))
    return text or "Not specified"


def _countries(protocol: dict[str, Any]) -> str:
    locations = protocol.get("contactsLocationsModule", {}).get("locations", []) or []
    countries: list[str] = []
    for item in locations:
        if isinstance(item, dict):
            country = _extract_text(item.get("country"))
            if country and country not in countries:
                countries.append(country)
    return ", ".join(countries) or "Not specified"


def _collaborators(protocol: dict[str, Any]) -> str:
    module = protocol.get("sponsorCollaboratorsModule", {})
    collaborators = module.get("collaborators", []) or []
    names: list[str] = []
    for item in collaborators:
        if isinstance(item, dict):
            name = _extract_text(item.get("name"))
            if name and name not in names:
                names.append(name)
    return ", ".join(names) or "None listed"


def _sponsor_type_from_name(name: str) -> str:
    text = (name or "").lower()
    if any(token in text for token in ["university", "hospital", "institute", "center", "centre", "m.d. anderson", "massachusetts general", "national cancer institute", "nih"]):
        return "Academic / government"
    if any(token in text for token in ["bristol", "merck", "astrazeneca", "genmab", "gilead", "pfizer", "roche", "novartis", "eli lilly", "abbvie", "bayer", "sanofi", "johnson"]):
        return "Large pharma / established oncology"
    if any(token in text for token in ["biotech", "pharma", "therapeutics", "bioscience", "medicines", "biopharma", "bio", "limited", "ltd", "inc", "llc", "gmbh"]):
        return "Biotech / emerging sponsor"
    return "Other sponsor"


def _record_from_study(study: dict[str, Any], spec: ClinicalTrialSearchSpec) -> TrialRecord | None:
    protocol = study.get("protocolSection", {}) if isinstance(study, dict) else {}
    nct_id = _nct_id(protocol)
    if not nct_id:
        return None
    status_module = protocol.get("statusModule", {})
    return TrialRecord(
        nct_id=nct_id,
        title=_title(protocol),
        sponsor=_sponsor(protocol),
        phase=_phase(protocol),
        status=_status(protocol),
        conditions=_conditions(protocol),
        interventions=_interventions(protocol),
        start_date=_first_date(status_module.get("startDateStruct")),
        last_update=_first_date(status_module.get("lastUpdatePostDateStruct")),
        source_query=spec.query,
        lane=spec.label,
        url=f"https://clinicaltrials.gov/study/{nct_id}",
        enrollment=_enrollment(protocol),
        primary_outcomes=_outcomes(protocol, "primaryOutcomes"),
        secondary_outcomes=_outcomes(protocol, "secondaryOutcomes"),
        observed_results=_observed_results(study),
        eligibility_criteria=_eligibility_criteria(protocol),
        countries=_countries(protocol),
        collaborators=_collaborators(protocol),
        sponsor_type=_sponsor_type_from_name(_sponsor(protocol)),
        query_family=getattr(spec, "query_family", "unknown"),
        query_area=getattr(spec, "query_area", "term"),
        discovery_queries=(f"{getattr(spec, 'query_family', 'unknown')}:{getattr(spec, 'query_area', 'term')}:{spec.query}",),
    )


def _request_payload(params: dict[str, str]) -> dict[str, Any]:
    url = f"{API_BASE}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "NextCure-Intelligence-Prototype/0.9.35"})
    with urlopen(request, timeout=CLINICAL_TRIALS_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed public API endpoint
        return json.loads(response.read().decode("utf-8"))


def _query_param_name(spec: ClinicalTrialSearchSpec) -> str:
    area = getattr(spec, "query_area", "term") or "term"
    return {
        "term": "query.term",
        "cond": "query.cond",
        "intr": "query.intr",
        "titles": "query.titles",
        "spons": "query.spons",
    }.get(area, "query.term")



def _record_haystack(record: TrialRecord) -> str:
    return " ".join([
        record.title, record.sponsor, record.conditions, record.interventions,
        record.primary_outcomes, record.secondary_outcomes, record.eligibility_criteria,
        record.collaborators, record.lane,
    ]).lower()


def _matched_retain_terms(record: TrialRecord, spec: ClinicalTrialSearchSpec) -> tuple[str, ...]:
    terms = tuple(getattr(spec, "retain_any_terms", ()) or ())
    if not terms:
        return ()
    haystack = _record_haystack(record)
    return tuple(dict.fromkeys(term for term in terms if str(term).lower() in haystack))


def _clinical_relevance_score(record: TrialRecord, spec: ClinicalTrialSearchSpec) -> tuple[int, tuple[str, ...]]:
    """Score retained records without using sponsor identity as a shortcut."""
    haystack = _record_haystack(record)
    matched = list(_matched_retain_terms(record, spec))
    score = len(matched)
    high_value = {
        "cdh6": 5, "cadherin": 5, "ds-6000": 5, "raludotatug": 5, "r-dxd": 5,
        "b7-h4": 4, "b7h4": 4, "vtcn1": 4,
        "adc": 3, "antibody-drug": 3, "conjugate": 2,
        "ovarian": 3, "fallopian": 2, "peritoneal": 2, "gynecologic": 2, "gynaecologic": 2,
        "folate": 2, "fr alpha": 2, "frα": 2, "trop2": 2, "her2": 1, "napi2b": 2,
    }
    for term, weight in high_value.items():
        if term in haystack:
            score += weight
            if term not in matched:
                matched.append(term)
    if any(token in haystack for token in ("objective response", "orr", "progression-free", "pfs", "duration of response", "dor")):
        score += 2
        matched.append("endpoint-language")
    if any(token in haystack for token in ("recruiting", "active, not recruiting", "not yet recruiting")):
        score += 1
    return score, tuple(dict.fromkeys(matched))


def _decorate_record(record: TrialRecord, spec: ClinicalTrialSearchSpec, fetched_pages: int, available_total: int | None) -> TrialRecord:
    score, matched = _clinical_relevance_score(record, spec)
    return replace(
        record,
        fetched_pages=fetched_pages,
        available_total=available_total,
        matched_fields=matched,
        relevance_score=score,
    )


def _retain_record(record: TrialRecord, spec: ClinicalTrialSearchSpec) -> bool:
    # Target/program searches are already narrow; broad disease/modality searches
    # must show at least one lane-relevant term in the returned payload.
    family = getattr(spec, "query_family", "") or ""
    if family in {"condition_broad_relevance_filtered"}:
        return bool(record.matched_fields) and record.relevance_score >= 3
    if family in {"broad_modality_context", "intervention_modality_context"}:
        return record.relevance_score >= 3
    return record.relevance_score > 0 or not getattr(spec, "retain_any_terms", ())


def _fetch_spec(spec: ClinicalTrialSearchSpec) -> tuple[list[TrialRecord], ClinicalTrialsDiscoveryAudit]:
    """Fetch a search spec with bounded pagination and audit metadata.

    This is the core recall-first change. Every query reports how many pages were
    fetched, how many raw records came back, how many were retained after lane
    relevance scoring, whether ClinicalTrials.gov indicated more pages were
    available, and any upstream error. Sponsor names are not used to decide
    retention.
    """
    query_param = _query_param_name(spec)
    base_params = {
        query_param: spec.query,
        "pageSize": str(CLINICAL_TRIALS_PAGE_SIZE),
        "format": "json",
        "countTotal": "true",
    }
    max_pages = min(int(getattr(spec, "max_pages", CLINICAL_TRIALS_MAX_PAGES_PER_SPEC) or 1), CLINICAL_TRIALS_MAX_PAGES_PER_SPEC)
    attempts = [
        base_params | {"sort": "LastUpdatePostDate:desc"},
        base_params,
    ]

    last_error = ""
    best_records: list[TrialRecord] = []
    fetched_pages = 0
    raw_count = 0
    available_total: int | None = None
    truncated = False

    for attempt_params in attempts:
        page_token: str | None = None
        page_records: list[TrialRecord] = []
        fetched_pages = 0
        raw_count = 0
        available_total = None
        truncated = False
        try:
            for _page in range(max_pages):
                params = dict(attempt_params)
                if page_token:
                    params["pageToken"] = page_token
                payload = _request_payload(params)
                fetched_pages += 1
                if available_total is None and payload.get("totalCount") is not None:
                    try:
                        available_total = int(payload.get("totalCount"))
                    except Exception:
                        available_total = None
                studies = payload.get("studies", []) or []
                raw_count += len(studies)
                for study in studies:
                    record = _record_from_study(study, spec)
                    if record is None:
                        continue
                    decorated = _decorate_record(record, spec, fetched_pages, available_total)
                    if _retain_record(decorated, spec):
                        page_records.append(decorated)
                page_token = str(payload.get("nextPageToken") or "").strip() or None
                if not page_token:
                    break
            truncated = bool(page_token)
            best_records = page_records
            last_error = ""
            break
        except Exception as exc:  # network/API failure should never break the dashboard
            last_error = f"{type(exc).__name__}: {exc}"
            best_records = []
            continue

    audit = ClinicalTrialsDiscoveryAudit(
        label=spec.label,
        query_family=getattr(spec, "query_family", "unknown"),
        query_area=getattr(spec, "query_area", "term"),
        query=spec.query,
        fetched_pages=fetched_pages,
        fetched_records=raw_count,
        retained_records=len(best_records),
        available_total=available_total,
        truncated=truncated,
        error=last_error,
    )
    return best_records, audit


def _merge_duplicate_records(existing: TrialRecord, incoming: TrialRecord, spec: ClinicalTrialSearchSpec) -> TrialRecord:
    existing_priority = next((s.priority for s in CLINICAL_TRIAL_SEARCH_SPECS if s.label == existing.lane), 99)
    incoming_priority = spec.priority
    primary = incoming if incoming_priority < existing_priority else existing
    secondary = existing if primary is incoming else incoming
    return replace(
        primary,
        discovery_queries=tuple(dict.fromkeys((*existing.discovery_queries, *incoming.discovery_queries))),
        matched_fields=tuple(dict.fromkeys((*existing.matched_fields, *incoming.matched_fields))),
        relevance_score=max(existing.relevance_score, incoming.relevance_score),
        fetched_pages=max(existing.fetched_pages, incoming.fetched_pages),
        available_total=max([v for v in (existing.available_total, incoming.available_total) if v is not None], default=None),
        source_query=primary.source_query,
    )


def _discovery_audit_table(audits: list[ClinicalTrialsDiscoveryAudit]) -> pd.DataFrame:
    columns = [
        "Lane", "Query Family", "Search Area", "Fetched Pages", "Fetched Records",
        "Retained Records", "Available Total", "Truncated", "Query", "Error",
    ]
    if not audits:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([
        {
            "Lane": a.label,
            "Query Family": a.query_family,
            "Search Area": a.query_area,
            "Fetched Pages": a.fetched_pages,
            "Fetched Records": a.fetched_records,
            "Retained Records": a.retained_records,
            "Available Total": "" if a.available_total is None else a.available_total,
            "Truncated": a.truncated,
            "Query": a.query,
            "Error": a.error,
        }
        for a in audits
    ])

def _is_active(status: str) -> bool:
    text = status.lower()
    return any(token in text for token in ["recruiting", "active", "enrolling", "not yet recruiting"])


def _trial_table(records: list[TrialRecord]) -> pd.DataFrame:
    columns = [
        "Lane", "NCT ID", "Sponsor", "Sponsor Type", "Phase", "Status", "Title",
        "Conditions", "Interventions", "Primary Outcomes", "Secondary Outcomes", "Posted Results",
        "Enrollment", "Countries", "Collaborators", "Start Date", "Last Update",
        "Query Family", "Matched Fields", "Relevance Score", "Discovery Provenance", "URL",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([
        {
            "Lane": r.lane,
            "NCT ID": r.nct_id,
            "Sponsor": r.sponsor,
            "Sponsor Type": r.sponsor_type,
            "Phase": r.phase,
            "Status": r.status,
            "Title": r.title,
            "Conditions": r.conditions,
            "Interventions": r.interventions,
            "Primary Outcomes": r.primary_outcomes,
            "Secondary Outcomes": r.secondary_outcomes,
            "Posted Results": r.observed_results,
            "Enrollment": r.enrollment,
            "Countries": r.countries,
            "Collaborators": r.collaborators,
            "Start Date": r.start_date,
            "Last Update": r.last_update,
            "Query Family": r.query_family,
            "Matched Fields": ", ".join(r.matched_fields),
            "Relevance Score": r.relevance_score,
            "Discovery Provenance": " | ".join(r.discovery_queries[:5]),
            "URL": r.url,
        }
        for r in records
    ])


def _summarize_lanes(records: list[TrialRecord]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for r in records:
        lane = summary.setdefault(r.lane, {"count": 0, "active": 0, "sponsors": set(), "phases": set()})
        lane["count"] += 1
        lane["active"] += 1 if _is_active(r.status) else 0
        lane["sponsors"].add(r.sponsor)
        lane["phases"].add(r.phase)
    for lane in summary.values():
        lane["sponsors"] = sorted(lane["sponsors"])
        lane["phases"] = sorted(lane["phases"])
    return summary



def _lane_records(records: list[TrialRecord], lane_name: str) -> list[TrialRecord]:
    return [r for r in records if r.lane == lane_name]


def _active_records(records: list[TrialRecord]) -> list[TrialRecord]:
    return [r for r in records if _is_active(r.status)]


def _unique_values(records: list[TrialRecord], attr: str, exclude: set[str] | None = None) -> list[str]:
    excluded = exclude or set()
    values: list[str] = []
    for r in records:
        raw = getattr(r, attr, "") or ""
        for part in [x.strip() for x in str(raw).split(",") if x.strip()]:
            if part not in excluded and part not in values:
                values.append(part)
    return values


def _sponsor_phrase(records: list[TrialRecord]) -> str:
    sponsors = _unique_values(records, "sponsor", {"Unknown sponsor"})
    if not sponsors:
        return "sponsor detail not clearly listed"
    return ", ".join(sponsors)


def _sponsor_type_mix(records: list[TrialRecord]) -> str:
    counts: dict[str, int] = {}
    for r in records:
        counts[r.sponsor_type] = counts.get(r.sponsor_type, 0) + 1
    ordered = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return "; ".join(f"{label}: {count}" for label, count in ordered) or "Sponsor type detail unavailable"


def _country_phrase(records: list[TrialRecord]) -> str:
    countries = _unique_values(records, "countries", {"Not specified"})
    if not countries:
        return "country/site geography not consistently listed"
    return ", ".join(countries)


def _enrollment_read(records: list[TrialRecord]) -> str:
    values: list[int] = []
    for r in records:
        try:
            values.append(int(float(str(r.enrollment).replace(",", ""))))
        except Exception:
            pass
    if not values:
        return "enrollment size was not consistently available across the surfaced records"
    return f"listed enrollment sizes range from {min(values):,} to {max(values):,}, with median-style midpoint around {sorted(values)[len(values)//2]:,}"


def _trial_text(r: TrialRecord) -> str:
    return " ".join([
        r.title, r.conditions, r.interventions, r.primary_outcomes, r.secondary_outcomes, r.observed_results,
        r.eligibility_criteria, r.countries, r.collaborators, r.sponsor, r.phase, r.status,
    ]).lower()


def _keyword_presence(records: list[TrialRecord], terms: list[str]) -> list[TrialRecord]:
    return [r for r in records if any(term.lower() in _trial_text(r) for term in terms)]


def _differentiation_reads(records: list[TrialRecord]) -> list[str]:
    if not records:
        return []
    reads: list[str] = []
    biomarker = _keyword_presence(records, ["biomarker", "expression", "positive", "selected", "selection", "stratified", "molecular", "ihc", "overexpress"])
    prior_therapy = _keyword_presence(records, ["platinum", "recurrent", "refractory", "resistant", "prior therapy", "previous therapy", "relapsed"])
    combo = _keyword_presence(records, ["combination", "combined", "pembrolizumab", "nivolumab", "paclitaxel", "carboplatin", "bevacizumab", "chemotherapy", "plus"])
    safety = _keyword_presence(records, ["safety", "tolerability", "dose limiting", "maximum tolerated", "recommended phase 2", "adverse event"])
    endpoints = _keyword_presence(records, ["overall response", "objective response", "progression-free", "duration of response", "dose limiting", "recommended phase 2"])

    if biomarker:
        reads.append(f"Patient-selection signal: {len(biomarker)} surfaced oncology record(s) contain biomarker, expression, positivity, or selection language. This is the part to watch because precision of patient selection is where a CDH6 story can become more than generic ADC exposure.")
    else:
        reads.append("Patient-selection signal: the surfaced oncology records did not consistently expose biomarker-selection language. That makes explicit CDH6 rationale and patient-selection clarity a potential messaging edge if supported by company data.")
    if prior_therapy:
        reads.append(f"Treatment-context signal: {len(prior_therapy)} record(s) reference recurrent, resistant, refractory, platinum, or prior-therapy language. That helps identify whether competitors are fighting in late-line salvage settings versus trying to move into cleaner earlier-line narratives.")
    if combo:
        reads.append(f"Combination signal: {len(combo)} record(s) include combination or partner-therapy language. If peers are leaning on combinations, a cleaner single-agent or better-tolerated positioning can become strategically important if the data support it.")
    if safety or endpoints:
        reads.append(f"Endpoint/safety signal: {len(set([r.nct_id for r in safety + endpoints]))} record(s) expose safety, tolerability, response, PFS, DOR, dose-limiting, or RP2D-style endpoint language. That is where the battlefield shifts from 'who has an ADC' to 'who can prove usable clinical benefit.'")
    return reads


def _phase_phrase(phases: list[str] | set[str]) -> str:
    clean = [p for p in sorted(phases) if p and p != "Not specified"]
    return ", ".join(clean[:4]) if clean else "phase detail not consistently specified"


def _clinical_activity_phrase(data: dict[str, Any], lane_name: str) -> str:
    active = int(data.get("active", 0) or 0)
    total = int(data.get("count", 0) or 0)
    label = _lane_label(lane_name)
    if total <= 0:
        return f"{label} did not contribute enough usable clinical signal to elevate this run"
    ratio = active / total
    if active >= 6 and ratio >= 0.75:
        return f"{label} is showing broad active clinical presence in this run"
    if active >= 3:
        return f"{label} remains meaningfully active in the current clinical sample"
    if active > 0:
        return f"{label} is present, but the signal is narrower than the larger monitored lanes"
    return f"{label} appeared in the clinical landscape, but active development was limited in this run"


def _phase_stage_phrase(phases: list[str] | set[str]) -> str:
    clean = {str(p).upper().replace(" ", "") for p in phases if p and p != "Not specified"}
    if any("PHASE3" in p for p in clean):
        return "the landscape includes late-stage programs, so the field is no longer purely exploratory"
    if any("PHASE2" in p for p in clean):
        return "mid-stage studies are present, which suggests the space is moving beyond first-in-human exploration"
    if any("PHASE1" in p for p in clean):
        return "the activity is still mostly early-stage, leaving room for differentiated clinical positioning"
    return "phase detail is inconsistent, so maturity should be interpreted cautiously"


def _maturity_label(phases: list[str] | set[str]) -> str:
    clean = {str(p).upper().replace(" ", "") for p in phases if p and p != "Not specified"}
    if any("PHASE3" in p for p in clean):
        return "late-stage anchor present"
    if any("PHASE2" in p for p in clean):
        return "mid-stage validation emerging"
    if any("PHASE1" in p for p in clean):
        return "early clinical field"
    return "maturity unclear"


def _theme_phrase(theme: str) -> str:
    mapping = {
        "biomarker / patient-selection language": "patient-selection / biomarker language",
        "combination strategy": "combination strategy",
        "ovarian / gynecologic focus": "ovarian / gynecologic focus",
        "antibody / ADC modality language": "antibody / ADC modality language",
    }
    return mapping.get(theme, theme)


def _theme_hits(records: list[TrialRecord]) -> dict[str, int]:
    theme_terms = {
        "biomarker / patient-selection language": ["biomarker", "expression", "positive", "selected", "selection", "stratified", "molecular"],
        "combination strategy": ["combination", "combined", "plus", "with pembrolizumab", "with chemotherapy", "with paclitaxel"],
        "ovarian / gynecologic focus": ["ovarian", "fallopian", "peritoneal", "gynecologic", "gynaecologic"],
        "antibody / ADC modality language": ["adc", "antibody drug", "antibody-drug", "antibody", "conjugate"],
    }
    counts = {theme: 0 for theme in theme_terms}
    for r in records:
        haystack = " ".join([r.title, r.conditions, r.interventions]).lower()
        for theme, terms in theme_terms.items():
            if any(term in haystack for term in terms):
                counts[theme] += 1
    return {theme: count for theme, count in counts.items() if count > 0}


def _top_theme_sentence(records: list[TrialRecord], scope: str) -> tuple[str, str] | None:
    hits = _theme_hits(records)
    if not hits:
        return None
    ranked = sorted(hits.items(), key=lambda item: item[1], reverse=True)
    top_theme, _ = ranked[0]
    other = [_theme_phrase(name) for name, _count in ranked[1:3]]
    detail = f"; secondary themes include {', '.join(other)}" if other else ""
    return (
        f"Across {scope}, the strongest repeated trial-design language is {_theme_phrase(top_theme)}{detail}.",
        "This matters because repeated protocol language reveals what sponsors are choosing to emphasize clinically, which is more useful than simply knowing that studies exist.",
    )


def _fragmentation_read(records: list[TrialRecord], lane_names: list[str]) -> str:
    lane_count = len(lane_names)
    sponsor_count = len({r.sponsor for r in records if r.sponsor and r.sponsor != "Unknown sponsor"})
    phases = {r.phase for r in records if r.phase and r.phase != "Not specified"}
    maturity = _phase_stage_phrase(phases)
    if sponsor_count >= 5 and lane_count >= 2:
        return (
            f"The direct oncology battlefield is active but fragmented across multiple sponsors; {maturity}. "
            "That is not automatically good or bad. The edge is to make the CDH6 / ovarian ADC story sharper than the category itself: why this target, why this patient population, and why the approach can stand out inside a crowded ADC conversation."
        )
    if sponsor_count >= 2:
        return (
            f"The direct oncology battlefield has multiple active sponsors but is not overwhelmingly broad in this sample; {maturity}. "
            "The edge is focus: use the clinical landscape to show that the category is alive while keeping the differentiation narrative specific to NextCure's own program rather than generic ADC momentum."
        )
    return (
        f"The direct oncology signal is present but narrow in this run; {maturity}. "
        "The edge is selectivity: avoid overstating category heat and instead emphasize the most defensible clinical angle supported by NextCure's own data and upcoming catalysts."
    )


def _latest_update_sentence(records: list[TrialRecord]) -> str | None:
    latest = sorted(_active_records(records), key=lambda r: r.last_update or "", reverse=True)[:4]
    if not latest:
        return None
    pieces = []
    for r in latest:
        phase = f", {r.phase}" if r.phase and r.phase != "Not specified" else ""
        pieces.append(f"{r.sponsor} — {_lane_label(r.lane)}{phase} [{r.nct_id}]")
    return "Recent clinical-record movement worth knowing: " + "; ".join(pieces) + "."


def _phase_mix(records: list[TrialRecord]) -> str:
    order = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"]
    counts: dict[str, int] = {}
    for r in records:
        phase = (r.phase or "Not specified").upper().replace(" ", "")
        counts[phase] = counts.get(phase, 0) + 1
    parts = []
    for key in order:
        if key in counts:
            parts.append(f"{key.replace('_', ' ')}: {counts[key]}")
    for key, val in sorted(counts.items()):
        if key not in order and key != "NOTSPECIFIED":
            parts.append(f"{key}: {val}")
    if counts.get("NOTSPECIFIED"):
        parts.append(f"phase not specified: {counts['NOTSPECIFIED']}")
    return "; ".join(parts) or "phase mix not available"


def _phase_anchor_sponsors(records: list[TrialRecord], phase_token: str = "PHASE3") -> list[str]:
    names: list[str] = []
    for r in records:
        if phase_token in (r.phase or "").upper().replace(" ", "") and r.sponsor not in names:
            names.append(r.sponsor)
    return names


def _lane_profile_sentence(records: list[TrialRecord], lane: str) -> str:
    lane_recs = _lane_records(records, lane)
    if not lane_recs:
        return f"{_lane_label(lane)}: no usable live clinical profile in this run."
    anchors = _phase_anchor_sponsors(lane_recs, "PHASE3")
    anchor_phrase = f" Late-stage anchor sponsor(s): {', '.join(anchors)}." if anchors else " No Phase 3 anchor was surfaced in this lane in this run."
    return (
        f"{_lane_label(lane)} profile — sponsors: {_sponsor_phrase(lane_recs)}. "
        f"Phase mix: {_phase_mix(lane_recs)}. "
        f"Sponsor mix: {_sponsor_type_mix(lane_recs)}. "
        f"Geography: {_country_phrase(lane_recs)}. "
        f"Enrollment signal: {_enrollment_read(lane_recs)}."
        f"{anchor_phrase}"
    )


def _battlefield_edge_sentence(ovarian_records: list[TrialRecord], b7h4_records: list[TrialRecord]) -> str:
    ovarian_anchors = _phase_anchor_sponsors(ovarian_records, "PHASE3")
    sponsor_mix = _sponsor_type_mix(ovarian_records) if ovarian_records else "Sponsor type detail unavailable"
    if ovarian_anchors:
        return (
            f"Ovarian ADC is not an empty or purely early-stage field; Phase 3 anchor sponsor(s) surfaced: {', '.join(ovarian_anchors)}. "
            f"The useful edge is not claiming first-mover category novelty. It is sharper CDH6-specific positioning inside a field that still shows sponsor fragmentation ({sponsor_mix}). "
            "That gives leadership a better board/investor framing: the category is validated enough to matter, but not so consolidated that a clear CDH6 rationale, patient-selection story, and catalyst path cannot stand out."
        )
    return (
        f"Ovarian ADC activity is visible but the current live pull did not surface a Phase 3 anchor inside the ovarian-linked set. Sponsor mix: {sponsor_mix}. "
        "That creates a different edge: the field is active enough to validate attention, while the clinical narrative may still be shaped by whoever can communicate the cleanest target rationale and patient-selection logic."
    )



def _sponsor_segments(records: list[TrialRecord]) -> str:
    buckets: dict[str, list[str]] = {
        "large pharma / established oncology": [],
        "biotech / emerging sponsor": [],
        "academic / government": [],
        "other sponsor": [],
    }
    for r in records:
        name = r.sponsor.strip() or "Unknown sponsor"
        if name == "Unknown sponsor":
            continue
        key = r.sponsor_type.lower()
        if "large pharma" in key:
            bucket = "large pharma / established oncology"
        elif "biotech" in key:
            bucket = "biotech / emerging sponsor"
        elif "academic" in key:
            bucket = "academic / government"
        else:
            bucket = "other sponsor"
        if name not in buckets[bucket]:
            buckets[bucket].append(name)
    parts = []
    for label, names in buckets.items():
        if names:
            parts.append(f"{label}: {', '.join(names)}")
    return "; ".join(parts) or "sponsor segmentation was not available"


def _endpoint_strategy_read(records: list[TrialRecord]) -> str:
    if not records:
        return "Endpoint strategy could not be assessed from the surfaced records."
    categories = {
        "response and tumor-control endpoints": ["objective response", "overall response", "orr", "response rate", "duration of response", "dor", "disease control"],
        "time-to-event endpoints": ["progression-free", "pfs", "overall survival", "os", "time to"],
        "dose/safety endpoints": ["safety", "tolerability", "dose limiting", "maximum tolerated", "recommended phase 2", "rp2d", "adverse event"],
    }
    hits: dict[str, list[str]] = {k: [] for k in categories}
    for r in records:
        haystack = " ".join([r.primary_outcomes, r.secondary_outcomes, r.title]).lower()
        for label, terms in categories.items():
            if any(term in haystack for term in terms) and r.nct_id not in hits[label]:
                hits[label].append(r.nct_id)
    ordered = [(label, ids) for label, ids in hits.items() if ids]
    if not ordered:
        return "Endpoint strategy is not consistently exposed in the surfaced records, so trial maturity should be judged more from phase, sponsor type, and enrollment design."
    phrases = [f"{label} in {len(ids)} study/studies" for label, ids in ordered]
    leader = max(ordered, key=lambda item: len(item[1]))[0]
    return f"Endpoint emphasis: {', '.join(phrases)}. The most visible endpoint posture is {leader}, which helps show whether competitors are optimizing for early activity signals, durability, or dose usability."


def _patient_selection_read(records: list[TrialRecord]) -> str:
    biomarker = _keyword_presence(records, ["biomarker", "expression", "positive", "selected", "selection", "stratified", "molecular", "ihc", "overexpress", "cdh6", "b7-h4", "b7h4"])
    prior = _keyword_presence(records, ["platinum", "recurrent", "refractory", "resistant", "relapsed", "prior therapy", "previous therapy", "after", "progressed"])
    if biomarker and prior:
        return f"Patient-selection read: {len({r.nct_id for r in biomarker})} study/studies expose biomarker, target-expression, or selection language and {len({r.nct_id for r in prior})} study/studies expose recurrent, refractory, resistant, platinum, relapsed, or prior-therapy language. The useful edge is seeing whether competitors are defining who should receive the ADC, not just whether they have an ADC."
    if biomarker:
        return f"Patient-selection read: {len({r.nct_id for r in biomarker})} study/studies expose biomarker, target-expression, or selection language. This is where a CDH6 story can become sharper than generic ovarian ADC exposure if the target rationale is communicated clearly."
    if prior:
        return f"Treatment-context read: {len({r.nct_id for r in prior})} study/studies expose recurrent, refractory, resistant, platinum, relapsed, or prior-therapy language. This helps separate late-line salvage positioning from broader ovarian oncology ambition."
    return "Patient-selection read: biomarker and treatment-line language were not strongly visible in the surfaced records. That absence itself matters because a clearer CDH6 patient-selection rationale can become more distinctive if supported by NextCure's own evidence."


def _combination_read(records: list[TrialRecord]) -> str:
    combo = _keyword_presence(records, ["combination", "combined", "pembrolizumab", "nivolumab", "paclitaxel", "carboplatin", "bevacizumab", "chemotherapy", "plus", "with"])
    if not combo:
        return "Combination read: the surfaced records do not strongly point to combination-heavy positioning. That keeps attention on target rationale, monotherapy activity, tolerability, and patient selection rather than assuming combinations are the main battlefield."
    return f"Combination read: {len({r.nct_id for r in combo})} study/studies contain combination or partner-therapy language. If competitors lean on combinations, the strategic question becomes whether a program can show cleaner single-agent contribution, better tolerability, or a clearer role in the treatment sequence."


def _geography_depth_read(records: list[TrialRecord]) -> str:
    countries = _unique_values(records, "countries", {"Not specified"})
    if not countries:
        return "Geography read: trial-site country detail was not consistently visible."
    regions = []
    lower = {c.lower() for c in countries}
    if "united states" in lower:
        regions.append("U.S.")
    if any(c in lower for c in {"china", "hong kong", "taiwan", "korea, republic of", "japan", "singapore"}):
        regions.append("Asia-Pacific")
    if any(c in lower for c in {"france", "germany", "spain", "italy", "united kingdom", "netherlands", "belgium", "poland"}):
        regions.append("Europe")
    region_phrase = f" Region signal: {', '.join(regions)}." if regions else ""
    return f"Geography read: surfaced countries include {', '.join(countries)}.{region_phrase} Broad geography can indicate operational seriousness; narrow geography can indicate earlier or more localized development."


def _enrollment_depth_read(records: list[TrialRecord]) -> str:
    values: list[tuple[int, TrialRecord]] = []
    for r in records:
        try:
            values.append((int(float(str(r.enrollment).replace(',', ''))), r))
        except Exception:
            pass
    if not values:
        return "Enrollment read: enrollment size was not consistently available, so confidence should lean more on phase, sponsor type, and protocol design."
    values.sort(key=lambda x: x[0], reverse=True)
    top_n = values[:3]
    top_text = "; ".join(f"{r.sponsor} {r.phase} {n:,} planned/actual participants" for n, r in top_n)
    return f"Enrollment read: the largest surfaced enrollment signals are {top_text}. Larger enrollment can indicate seriousness or later-stage breadth; smaller enrollment often points to exploratory signal-finding."


def _board_ammunition_read(records: list[TrialRecord]) -> str:
    if not records:
        return "No board-level clinical ammunition was available from this source run."
    sponsors = _sponsor_segments(records)
    endpoint = _endpoint_strategy_read(records)
    selection = _patient_selection_read(records)
    combo = _combination_read(records)
    return (
        "Board/investor ammunition from ClinicalTrials.gov: "
        f"1) sponsor map — {sponsors}. "
        f"2) {endpoint} "
        f"3) {selection} "
        f"4) {combo}"
    )


def _edge_read(records: list[TrialRecord], lane_name: str) -> str:
    lane_recs = _lane_records(records, lane_name)
    if not lane_recs:
        return f"{_lane_label(lane_name)}: no edge read available from this run."
    phase3 = _phase_anchor_sponsors(lane_recs, "PHASE3")
    phase2 = _phase_anchor_sponsors(lane_recs, "PHASE2")
    sponsors = _unique_values(lane_recs, "sponsor", {"Unknown sponsor"})
    sponsor_count = len(sponsors)
    if phase3 and sponsor_count >= 4:
        setup = f"{_lane_label(lane_name)} has late-stage anchor sponsor(s) ({', '.join(phase3)}) plus a broader sponsor set ({', '.join(sponsors)})."
        edge = "That points to a validated but contested field: the edge is not novelty; the edge is whether NextCure can make CDH6 feel more precise, more biologically justified, and better timed than broad ADC category exposure."
    elif phase2 or phase3:
        anchors = phase3 or phase2
        setup = f"{_lane_label(lane_name)} has visible mid/late clinical anchors ({', '.join(anchors)}) but does not look fully consolidated in this pull."
        edge = "That creates room for a differentiated clinical narrative if NextCure can clearly explain target selection, patient fit, and evidence path."
    else:
        setup = f"{_lane_label(lane_name)} appears active but mainly earlier-stage in this pull, with sponsors including {', '.join(sponsors)}."
        edge = "That is a shapeable battlefield: the edge is establishing clinical credibility and narrative specificity before the space becomes more crowded or later-stage."
    return f"{setup} {edge}"


def _edge_read_for_records(label: str, lane_recs: list[TrialRecord]) -> str:
    if not lane_recs:
        return f"{label}: no edge read available from this run."
    phase3 = _phase_anchor_sponsors(lane_recs, "PHASE3")
    phase2 = _phase_anchor_sponsors(lane_recs, "PHASE2")
    sponsors = _unique_values(lane_recs, "sponsor", {"Unknown sponsor"})
    sponsor_count = len(sponsors)
    if phase3 and sponsor_count >= 4:
        setup = f"{label} has late-stage anchor sponsor(s) ({', '.join(phase3)}) plus a broader sponsor set ({', '.join(sponsors)})."
        edge = "That points to a validated but contested field: the edge is not novelty; the edge is whether NextCure can make CDH6 feel more precise, more biologically justified, and better timed than broad ADC category exposure."
    elif phase2 or phase3:
        anchors = phase3 or phase2
        setup = f"{label} has visible mid/late clinical anchors ({', '.join(anchors)}) but does not look fully consolidated in this pull."
        edge = "That creates room for a differentiated clinical narrative if NextCure can clearly explain target selection, patient fit, and evidence path."
    else:
        setup = f"{label} appears active but mainly earlier-stage in this pull, with sponsors including {', '.join(sponsors)}."
        edge = "That is a shapeable battlefield: the edge is establishing clinical credibility and narrative specificity before the space becomes more crowded or later-stage."
    return f"{setup} {edge}"



# --- v0.9.26: adaptive leverage upgrade clinical intelligence helpers ---


@dataclass(frozen=True)
class ClinicalLaneSignature:
    """Adaptive strategic state derived from combinations of ClinicalTrials.gov fields.

    The signature exists to prevent the Executive Summary from becoming a trial
    database narration. It compresses raw fields into a confidence-weighted
    battlefield read that can change as the live pull changes.
    """

    label: str
    sponsors: list[str]
    phase3_sponsors: list[str]
    phase2_sponsors: list[str]
    phase1_sponsors: list[str]
    sponsor_types: dict[str, list[str]]
    patient_selection_strength: str
    combination_strength: str
    safety_strength: str
    response_strength: str
    geography_strength: str
    enrollment_strength: str
    strategic_state: str
    narrative_owner: str
    edge_thesis: str
    proof_burden: str
    investor_question: str
    signature_codes: list[str]
    priority_score: int
    confidence: str
    confidence_reason: str


def _sponsors_for_phase(records: list[TrialRecord], token: str) -> list[str]:
    token = token.upper().replace(" ", "")
    names: list[str] = []
    for r in records:
        phase = (r.phase or "").upper().replace(" ", "")
        if token in phase and r.sponsor not in names and r.sponsor != "Unknown sponsor":
            names.append(r.sponsor)
    return names


def _unique_sponsors(records: list[TrialRecord]) -> list[str]:
    return _unique_values(records, "sponsor", {"Unknown sponsor"})


def _sponsor_type_buckets(records: list[TrialRecord]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "established oncology/pharma": [],
        "emerging/specialist developers": [],
        "academic/government": [],
        "other named sponsors": [],
    }
    for r in records:
        name = (r.sponsor or "").strip()
        if not name or name == "Unknown sponsor":
            continue
        sponsor_type = r.sponsor_type.lower()
        if "large pharma" in sponsor_type:
            key = "established oncology/pharma"
        elif "biotech" in sponsor_type:
            key = "emerging/specialist developers"
        elif "academic" in sponsor_type:
            key = "academic/government"
        else:
            key = "other named sponsors"
        if name not in buckets[key]:
            buckets[key].append(name)
    return {k: v for k, v in buckets.items() if v}


def _signal_records(records: list[TrialRecord], terms: list[str]) -> list[TrialRecord]:
    return _keyword_presence(records, terms)


def _signal_strength(records: list[TrialRecord], terms: list[str]) -> tuple[str, list[TrialRecord]]:
    hits = _signal_records(records, terms)
    unique = {r.nct_id for r in hits}
    if not records:
        return "not assessable", []
    ratio = len(unique) / max(1, len({r.nct_id for r in records}))
    if len(unique) >= 3 and ratio >= 0.45:
        return "prominent", hits
    if unique:
        return "present", hits
    return "not prominent", []


def _geography_strength(records: list[TrialRecord]) -> str:
    countries = _unique_values(records, "countries", {"Not specified"})
    if len(countries) >= 12:
        return "global / operationally broad"
    if len(countries) >= 4:
        return "multi-region"
    if countries:
        return "localized / narrower"
    return "not clearly exposed"


def _enrollment_strength(records: list[TrialRecord]) -> str:
    values: list[int] = []
    for r in records:
        try:
            values.append(int(float(str(r.enrollment).replace(",", ""))))
        except Exception:
            pass
    if not values:
        return "not clearly exposed"
    if max(values) >= 500:
        return "large-scale enrollment visible"
    if max(values) >= 150:
        return "mid-sized enrollment visible"
    return "small / signal-finding enrollment"


def _phase_architecture_short_from_sig(sig: ClinicalLaneSignature) -> str:
    parts: list[str] = []
    if sig.phase3_sponsors:
        parts.append(f"Phase 3 anchor: {', '.join(sig.phase3_sponsors)}")
    if sig.phase2_sponsors:
        parts.append(f"Phase 2/mid-stage: {', '.join(sig.phase2_sponsors)}")
    if sig.phase1_sponsors:
        parts.append(f"early-stage: {', '.join(sig.phase1_sponsors)}")
    return "; ".join(parts) if parts else "phase architecture not clearly exposed"


def _sponsor_segment_text(sig: ClinicalLaneSignature) -> str:
    if not sig.sponsor_types:
        return "sponsor segmentation unavailable"
    return "; ".join(f"{label}: {', '.join(names)}" for label, names in sig.sponsor_types.items())


def _narrative_owner_label(records: list[TrialRecord]) -> str:
    sponsors = _unique_sponsors(records)
    phase3 = _sponsors_for_phase(records, "PHASE3")
    established = _sponsor_type_buckets(records).get("established oncology/pharma", [])
    if len(phase3) >= 2:
        return "late-stage ownership is contested rather than controlled by one sponsor"
    if len(phase3) == 1 and len(sponsors) >= 4:
        return f"{phase3[0]} is the late-stage reference point, but the lane is not fully owned"
    if len(phase3) == 1:
        return f"{phase3[0]} is the clearest late-stage reference point"
    if len(established) >= 2 and len(sponsors) >= 5:
        return "large oncology sponsors are present, but no single late-stage owner surfaced"
    if len(sponsors) >= 4:
        return "multiple sponsors are active, but no clear narrative owner surfaced"
    return "narrative ownership remains early or unclear"


def _confidence_from_codes(codes: list[str], records: list[TrialRecord], label: str) -> tuple[str, str]:
    evidence_count = len({r.nct_id for r in records})
    if not records:
        return "low", "no usable lane records were surfaced"
    high_codes = {"late_stage_anchor", "sponsor_fragmentation", "patient_selection_visible"}
    if evidence_count >= 4 and len(high_codes.intersection(codes)) >= 2:
        return "high", "phase, sponsor, and protocol signals point in the same direction"
    if evidence_count >= 2 and codes:
        return "moderate", "the signal is supported by multiple records but should still be monitored for confirmation"
    return "low", "the read is preliminary and should not carry the executive conclusion alone"


def _derive_lane_signature(label: str, records: list[TrialRecord]) -> ClinicalLaneSignature | None:
    if not records:
        return None

    sponsors = _unique_sponsors(records)
    phase3 = _sponsors_for_phase(records, "PHASE3")
    phase2 = _sponsors_for_phase(records, "PHASE2")
    phase1 = _sponsors_for_phase(records, "PHASE1")
    sponsor_types = _sponsor_type_buckets(records)
    patient_strength, _ = _signal_strength(records, [
        "biomarker", "expression", "positive", "selected", "selection", "stratified", "molecular", "ihc", "overexpress", "cdh6", "b7-h4", "b7h4"
    ])
    combo_strength, _ = _signal_strength(records, [
        "combination", "combined", "pembrolizumab", "nivolumab", "paclitaxel", "carboplatin", "bevacizumab", "chemotherapy", " plus ", " with "
    ])
    safety_strength, _ = _signal_strength(records, [
        "safety", "tolerability", "dose limiting", "maximum tolerated", "recommended phase 2", "rp2d", "adverse event"
    ])
    response_strength, _ = _signal_strength(records, [
        "objective response", "overall response", "orr", "duration of response", "dor", "progression-free", "pfs", "overall survival"
    ])
    geography = _geography_strength(records)
    enrollment = _enrollment_strength(records)
    owner = _narrative_owner_label(records)

    sponsor_count = len(sponsors)
    phase3_count = len(phase3)
    codes: list[str] = []
    score = 0

    if phase3_count:
        codes.append("late_stage_anchor")
        score += 3
    if sponsor_count >= 4:
        codes.append("sponsor_fragmentation")
        score += 2
    if patient_strength in {"prominent", "present"}:
        codes.append("patient_selection_visible")
        score += 2
    if combo_strength in {"prominent", "present"}:
        codes.append("combination_context_visible")
        score += 1
    if safety_strength in {"prominent", "present"}:
        codes.append("usability_burden_visible")
        score += 1
    if response_strength in {"prominent", "present"}:
        codes.append("efficacy_burden_visible")
        score += 1
    if geography in {"multi-region", "global / operationally broad"}:
        codes.append("operational_breadth")
        score += 1

    label_lower = label.lower()
    if label.startswith("CDH6"):
        if phase3_count == 1 and sponsor_count >= 4:
            state = "validated but still shapeable"
            edge = "A single late-stage anchor validates CDH6, while the broader sponsor map still leaves room for target-specific narrative ownership."
        elif phase3_count >= 2:
            state = "validated and increasingly contested"
            edge = "CDH6 would need to compete on patient definition, clinical usability, and evidence quality rather than category participation."
        elif sponsor_count >= 4:
            state = "active but not late-stage-owned"
            edge = "CDH6 remains narrative-open if the target rationale can be made clearer than the broader ovarian ADC field."
        else:
            state = "early and narrative-open"
            edge = "CDH6 is still early enough that credible biology and patient definition can help define what the lane means."
    elif "b7-h4" in label_lower:
        state = "gynecologic-oncology read-through"
        edge = "B7-H4 is useful gynecologic-oncology read-through, but it should not be blended into the CDH6 thesis."
    elif "ovarian adc" in label_lower:
        state = "category validation with noise"
        edge = "Broad ovarian ADC activity validates investor attention, but it also creates noise that CDH6 positioning must cut through."
    elif "adc oncology" in label_lower:
        state = "category weather"
        edge = "Broad ADC oncology activity can explain modality appetite, but it should not replace the target-specific answer."
    else:
        state = "exploratory context"
        edge = "This lane is useful as optionality context, not as the core oncology positioning thesis."

    proof_parts: list[str] = []
    if patient_strength == "prominent":
        proof_parts.append("patient-selection logic is prominent, so target-expression credibility becomes a differentiator")
    elif patient_strength == "present":
        proof_parts.append("patient-selection logic is present, so the target rationale needs to be explicit")
    if combo_strength == "prominent":
        proof_parts.append("combination language is prominent, so single-agent contribution, tolerability, or sequencing can become a counter-position")
    elif combo_strength == "present":
        proof_parts.append("combination language is present, so treatment-sequence clarity matters")
    if safety_strength in {"prominent", "present"}:
        proof_parts.append("dose, safety, and tolerability remain visible proof burdens")
    if response_strength in {"prominent", "present"}:
        proof_parts.append("response, durability, and time-to-event endpoints keep the burden on usable benefit")
    proof = "; ".join(proof_parts) if proof_parts else "the proof burden remains target rationale, patient fit, response durability, and clinical timing"

    if label.startswith("CDH6") and phase3_count == 1:
        question = "How can CDH6 use Daiichi's late-stage presence as validation without conceding the whole narrative?"
    elif label.startswith("CDH6") and phase3_count >= 2:
        question = "How does the company avoid sounding late to an increasingly validated CDH6 field?"
    elif label.startswith("CDH6"):
        question = "Can the company define CDH6 before the field becomes more crowded or later-stage?"
    elif "B7-H4" in label:
        question = "How should B7-H4 be used as attention read-through without confusing it with CDH6?"
    elif "ovarian ADC" in label_lower:
        question = "How much of ovarian ADC activity is useful context versus category noise?"
    else:
        question = "Does this activity change the core thesis, or is it only context?"

    confidence, confidence_reason = _confidence_from_codes(codes, records, label)

    return ClinicalLaneSignature(
        label=label,
        sponsors=sponsors,
        phase3_sponsors=phase3,
        phase2_sponsors=phase2,
        phase1_sponsors=phase1,
        sponsor_types=sponsor_types,
        patient_selection_strength=patient_strength,
        combination_strength=combo_strength,
        safety_strength=safety_strength,
        response_strength=response_strength,
        geography_strength=geography,
        enrollment_strength=enrollment,
        strategic_state=state,
        narrative_owner=owner,
        edge_thesis=edge,
        proof_burden=proof,
        investor_question=question,
        signature_codes=codes,
        priority_score=score,
        confidence=confidence,
        confidence_reason=confidence_reason,
    )


def _signature_evidence(sig: ClinicalLaneSignature) -> str:
    return (
        f"Sponsors: {', '.join(sig.sponsors) if sig.sponsors else 'none surfaced'}. "
        f"{_phase_architecture_short_from_sig(sig)}. "
        f"Sponsor segmentation: {_sponsor_segment_text(sig)}. "
        f"Signals: {', '.join(sig.signature_codes) if sig.signature_codes else 'no high-conviction signature'}; "
        f"patient selection: {sig.patient_selection_strength}; combinations: {sig.combination_strength}; "
        f"safety/tolerability: {sig.safety_strength}; response/durability: {sig.response_strength}; "
        f"geography: {sig.geography_strength}; enrollment: {sig.enrollment_strength}; confidence: {sig.confidence}."
    )


def _evidence_tag(sig: ClinicalLaneSignature) -> str:
    return f"Confidence: {sig.confidence}. Evidence basis: {sig.confidence_reason}."


def _sponsor_tier_context(sig: ClinicalLaneSignature) -> str:
    """Turn sponsor names into meaning instead of dumping them repeatedly."""
    if not sig.sponsor_types:
        return "sponsor mix is not clearly exposed"
    parts: list[str] = []
    established = sig.sponsor_types.get("established oncology/pharma", [])
    emerging = sig.sponsor_types.get("emerging/specialist developers", [])
    academic = sig.sponsor_types.get("academic/government", [])
    other = sig.sponsor_types.get("other named sponsors", [])
    if established:
        parts.append(f"established oncology/pharma ({', '.join(established)})")
    if emerging:
        parts.append(f"specialist or emerging developers ({', '.join(emerging)})")
    if academic:
        parts.append(f"academic/government participation ({', '.join(academic)})")
    if other:
        parts.append(f"other named sponsors ({', '.join(other)})")
    return "; ".join(parts)


def _primary_leverage_from_signature(sig: ClinicalLaneSignature) -> str:
    """Derive the highest-value leverage point from the signature constellation."""
    if sig.label.startswith("CDH6"):
        if "late_stage_anchor" in sig.signature_codes and "sponsor_fragmentation" in sig.signature_codes:
            if sig.patient_selection_strength in {"prominent", "present"}:
                return "target-specific patient definition: use Daiichi as clinical validation while avoiding a generic ADC frame"
            return "narrative ownership: the lane is validated, but no single sponsor fully owns the CDH6 story"
        if sig.patient_selection_strength in {"prominent", "present"}:
            return "making CDH6 biology and target expression feel more precise than broad ovarian ADC participation"
        return "defining the CDH6 lane before it becomes more crowded or more late-stage"
    if "B7-H4" in sig.label:
        return "comparative discipline: use B7-H4 to explain gynecologic-oncology attention without letting it blur the CDH6 thesis"
    if "Broad ovarian" in sig.label:
        return "category separation: ovarian ADC activity validates investor attention, but also creates noise that a CDH6-specific thesis must cut through"
    return sig.edge_thesis


def _proof_leverage_sentence(sig: ClinicalLaneSignature) -> str:
    pieces: list[str] = []
    if sig.patient_selection_strength == "prominent":
        pieces.append("patient-selection language is prominent, so the differentiator is not merely claiming selected patients; it is owning the most credible target-expression rationale")
    elif sig.patient_selection_strength == "present":
        pieces.append("patient-selection language is present, so the target rationale must be explicit enough to avoid generic ADC positioning")
    if sig.combination_strength == "prominent":
        pieces.append("combination language is prominent, which may leave room for a cleaner single-agent, sequencing, or tolerability counter-position if supported by data")
    elif sig.combination_strength == "present":
        pieces.append("combination language is present, so treatment-sequence clarity matters")
    if sig.safety_strength in {"prominent", "present"}:
        pieces.append("dose, safety, and tolerability remain part of the real proof burden")
    if sig.response_strength in {"prominent", "present"}:
        pieces.append("response, durability, and time-to-event endpoints keep the story anchored to usable clinical benefit")
    return "; ".join(pieces) if pieces else sig.proof_burden


def _clinical_leverage_thesis(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q1: state the plain-English finding, not the full strategy."""
    if cdh6_sig:
        phase_anchor = cdh6_sig.phase3_sponsors[0] if cdh6_sig.phase3_sponsors else None
        if phase_anchor:
            return (
                f"Daiichi Sankyo is the main late-stage CDH6 reference point in the current clinical pull. "
                "The rest of the CDH6 activity is earlier-stage and spread across multiple sponsors, which means CDH6 is clinically credible but not yet controlled by one dominant story. "
                "That is the key finding: there may still be room for a clearer CDH6-specific explanation of which patients benefit and why."
            )
        return (
            "CDH6-linked activity surfaced, but without a clear late-stage owner in this pull. "
            "That makes the evidence burden higher, but it also means the target story is still open to be defined if the biology and patient fit are made clear."
        )
    if ovarian_sig:
        return (
            "Ovarian ADC activity remains active in the current clinical pull, but the signal is broad. "
            "It supports category interest without, by itself, creating a company-specific CDH6 story."
        )
    if b7h4_sig:
        return (
            "B7-H4 activity surfaced as nearby gynecologic-oncology context. "
            "It is useful for understanding attention around adjacent targets, but it does not answer the CDH6 question."
        )
    return "The live clinical pull did not create a high-conviction direct ovarian/CDH6 clinical read this run."

def _recent_movement_read(records: list[TrialRecord]) -> str | None:
    direct_lanes = {"CDH6 / Ovarian ADC", "B7-H4 ADC", "Ovarian ADC"}
    direct_latest = sorted(_active_records([r for r in records if r.lane in direct_lanes]), key=lambda r: r.last_update or "", reverse=True)[:3]
    if not direct_latest:
        return None
    pieces = [f"{r.sponsor} ({_lane_label(r.lane)} {r.phase}; {r.nct_id})" for r in direct_latest]
    return "Recent direct oncology movement worth having ready: " + "; ".join(pieces) + "."


def _investor_ammunition_read(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q2: translate the field structure into plain investor ammunition."""
    if cdh6_sig:
        phase_anchor = cdh6_sig.phase3_sponsors[0] if cdh6_sig.phase3_sponsors else None
        if phase_anchor:
            lead = (
                f"The useful investor answer is simple: {phase_anchor} helps validate CDH6, but it does not mean every CDH6 story has already been won. "
                "The opening is to explain why CDH6 matters for a specific patient group, not to argue that ovarian ADCs are popular."
            )
        else:
            lead = (
                "The useful investor answer is that CDH6 is still an open lane, but open lanes require sharper explanation. "
                "The company has to make the biology, patient fit, and evidence path easy to understand."
            )
        context = []
        if ovarian_sig:
            context.append("Broad ovarian ADC activity helps show the category is relevant, but it is too broad to be the whole story.")
        if b7h4_sig:
            context.append("B7-H4 helps explain attention around neighboring gynecologic-oncology targets, but it should not blur the CDH6 message.")
        return " ".join([lead] + context).strip()
    if ovarian_sig:
        return "The useful investor answer is category discipline: ovarian ADC activity supports attention, but it only becomes company-specific when tied to a clear target and patient rationale."
    if b7h4_sig:
        return "The useful investor answer is comparator discipline: B7-H4 explains adjacent attention, but it should not be treated as the CDH6 thesis."
    return "No high-priority direct oncology ammunition surfaced in this clinical run."

def _proof_burden_read(sig: ClinicalLaneSignature | None) -> str | None:
    """Q2 support: quantified evidence + implication from the lane signature."""
    if sig is None:
        return None
    # Reconstruct the relevant lane records from the global signal evidence later by passing
    # through a label lookup at call site is cleaner long-term, but for this current
    # signature-only function we keep the qualitative burden. Quantified evidence is
    # emitted by _clinical_evidence_pack_read where records are available.
    burdens: list[str] = []
    if sig.patient_selection_strength in {"prominent", "present"}:
        burdens.append("which patients should be CDH6-defined and why")
    if sig.combination_strength in {"prominent", "present"}:
        burdens.append("whether benefit is clear enough without getting lost inside combination therapy")
    if sig.safety_strength in {"prominent", "present"}:
        burdens.append("whether dosing and tolerability make real treatment use believable")
    if sig.response_strength in {"prominent", "present"}:
        burdens.append("whether response and durability are strong enough to matter")
    if not burdens:
        burdens.append("whether CDH6 can separate itself from broader ADC noise")
    if len(burdens) == 1:
        burden_text = burdens[0]
    else:
        burden_text = ", ".join(burdens[:-1]) + f", and {burdens[-1]}"
    return f"What investors will press on: {burden_text}."


def _clinical_evidence_pack_read(records: list[TrialRecord], label: str = "the surfaced lane") -> str | None:
    """Evidence-linked adaptive fragment: numbers when available, no invented efficacy."""
    if not records:
        return None
    pieces = []
    selection = _selection_combo_number_read(records)
    endpoints = _endpoint_number_read(records)
    posted = _posted_results_read(records)
    if selection:
        pieces.append(selection)
    if endpoints:
        pieces.append(endpoints)
    if posted:
        pieces.append(posted)
    if not pieces:
        return None
    implication = (
        "Interpretation: endpoint counts describe what studies are designed to measure, not what they have already proven. "
        "Posted outcome values, when available, are treated separately so the system does not confuse protocol intent with observed efficacy."
    )
    return f"Clinical evidence pack for {label}: " + " ".join(pieces) + " " + implication


def _trend_line(sig: ClinicalLaneSignature, role: str) -> str:
    """Q3: plain trend translation, not jargon."""
    phase = _phase_architecture_short_from_sig(sig)
    if sig.label.startswith("CDH6"):
        return (
            f"CDH6 / ovarian ADC: one late-stage reference point gives the target credibility, but the field still has room for someone to explain CDH6 better than the pack. {phase}. "
            "The trend to watch is whether future data make CDH6 a clear patient-selection story rather than just another ovarian ADC program."
        )
    if "Broad ovarian ADC" in sig.label:
        return (
            f"Broad ovarian ADC: the category is active, but that also makes it harder to stand out. {phase}. "
            "The trend to watch is whether investors reward broad ovarian ADC exposure or start demanding sharper target-level explanations."
        )
    if "B7-H4" in sig.label:
        return (
            f"B7-H4: this remains a nearby gynecologic-oncology attention lane, not a replacement for CDH6. {phase}. "
            "The trend to watch is whether B7-H4 keeps pulling attention toward adjacent targets or simply reinforces broader interest in gynecologic oncology."
        )
    return f"{sig.label}: {sig.strategic_state}. {role}: {_primary_leverage_from_signature(sig)}. {phase}."

def _trend_lines_from_signatures(signatures: list[ClinicalLaneSignature]) -> list[str]:
    # Progressive hierarchy: CDH6 first when present, then category context, then comparator.
    by_label = {s.label: s for s in signatures}
    ordered: list[ClinicalLaneSignature] = []
    for label in ["CDH6 / ovarian ADC", "Broad ovarian ADC", "B7-H4 ADC"]:
        sig = by_label.get(label)
        if sig:
            ordered.append(sig)
    ordered.extend([s for s in sorted(signatures, key=lambda s: s.priority_score, reverse=True) if s not in ordered])
    lines: list[str] = []
    for sig in ordered:
        if sig.label.startswith("CDH6"):
            lines.append(_trend_line(sig, "Core clinical read"))
        elif "Broad ovarian ADC" in sig.label:
            lines.append(_trend_line(sig, "Category context"))
        elif "B7-H4" in sig.label:
            lines.append(_trend_line(sig, "Comparator context"))
    return lines


def _positioning_line(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q4: connect market behavior to the simplest CDH6 positioning line."""
    if cdh6_sig:
        phase_anchor = cdh6_sig.phase3_sponsors[0] if cdh6_sig.phase3_sponsors else None
        if phase_anchor:
            return (
                f"NXTC should not be explained as generic ADC exposure. A cleaner line is: {phase_anchor} helps prove CDH6 is worth taking seriously, but there is still room to define the CDH6 story around the right patients, the right biology, and the quality of the evidence. "
                "That is the positioning gap to close if the recent stock move is going to become more than a short-term bounce."
            )
        return (
            "NXTC's cleanest positioning is CDH6 specificity rather than broad ADC exposure. "
            "The market needs a simple reason to treat the target story as different from the broader ovarian ADC backdrop."
        )
    if ovarian_sig:
        return "NXTC should be judged against an active ovarian ADC backdrop, but the market still needs a target-specific reason to separate the company from broad modality exposure."
    if b7h4_sig:
        return "B7-H4 provides useful nearby attention, but it should not replace a company-specific CDH6 positioning answer."
    return "The live clinical pull did not create a strong direct positioning read this run."

def _db_hook_evidence(records: list[TrialRecord]) -> str:
    return f"Structured ClinicalTrials.gov records preserved for future longitudinal database comparison: {len(records)}."




# --- v0.9.31: fully adaptive fragment compiler ---
# These overrides intentionally move the Executive Summary away from curated
# paragraphs. Each line is assembled from the current clinical signature state:
# phase anchors, sponsor spread, patient-selection language, combination burden,
# safety/usability endpoints, and comparator lanes. If tomorrow's ClinicalTrials.gov
# pull changes those fields, the emitted fragments change with it.


def _tiered_sponsor_summary(names: list[str], sponsor_types: dict[str, list[str]], max_examples: int = 3) -> str:
    """Condense sponsor lists into executive-tier language instead of dumping names."""
    if not names:
        return "no named sponsors"
    if len(names) <= max_examples:
        return ", ".join(names)

    pieces: list[str] = []
    for tier, tier_names in sponsor_types.items():
        overlap = [n for n in tier_names if n in names]
        if not overlap:
            continue
        examples = ", ".join(overlap[:2])
        suffix = f" including {examples}" if examples else ""
        pieces.append(f"{len(overlap)} {tier}{suffix}")
    if pieces:
        return "; ".join(pieces)
    return f"{len(names)} named sponsors, led by {', '.join(names[:max_examples])}"


def _phase_role_fragment(sig: ClinicalLaneSignature) -> str:
    if sig.phase3_sponsors:
        anchor = _tiered_sponsor_summary(sig.phase3_sponsors, sig.sponsor_types)
        if len(sig.phase3_sponsors) == 1:
            return f"{anchor} is the only Phase 3 sponsor surfaced"
        return f"Phase 3 activity spans {anchor}"
    if sig.phase2_sponsors:
        return f"mid-stage activity spans {_tiered_sponsor_summary(sig.phase2_sponsors, sig.sponsor_types)}"
    if sig.phase1_sponsors:
        return f"activity is still mainly early-stage across {_tiered_sponsor_summary(sig.phase1_sponsors, sig.sponsor_types)}"
    return "phase leadership was not clear in this pull"


def _earlier_sponsor_fragment(sig: ClinicalLaneSignature) -> str:
    anchors = set(sig.phase3_sponsors)
    earlier = [name for name in sig.sponsors if name not in anchors]
    if not earlier:
        return "no separate earlier-stage sponsor group was clearly surfaced"
    return f"earlier-stage activity remains spread across {_tiered_sponsor_summary(earlier, sig.sponsor_types)}"


def _ownership_state(sig: ClinicalLaneSignature) -> str:
    if sig.phase3_sponsors and len(sig.sponsors) >= 4:
        return "no one clearly owns the whole story yet"
    if len(sig.phase3_sponsors) >= 2:
        return "late-stage leadership is contested"
    if sig.phase3_sponsors:
        return "the late-stage story is concentrated around one sponsor"
    if len(sig.sponsors) >= 4:
        return "the lane is active but still lacks a clear leader"
    return "the lane is still early enough that the story remains open"


def _clinical_leverage_thesis(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q1: adaptive observation, not an essay."""
    if cdh6_sig:
        return (
            f"CDH6: {_phase_role_fragment(cdh6_sig)}, while {_earlier_sponsor_fragment(cdh6_sig)}. "
            f"The practical read is simple: CDH6 is real enough to discuss seriously, but {_ownership_state(cdh6_sig)}."
        )
    if ovarian_sig:
        return (
            f"Ovarian ADC: {_phase_role_fragment(ovarian_sig)}. "
            "This supports category interest, but it does not by itself explain a CDH6-specific edge."
        )
    if b7h4_sig:
        return (
            f"B7-H4: {_phase_role_fragment(b7h4_sig)}. "
            "This is nearby gynecologic-oncology context, not the CDH6 answer."
        )
    return "No high-conviction CDH6, ovarian ADC, or B7-H4 clinical signal was strong enough to elevate this run."


def _recent_movement_read(records: list[TrialRecord]) -> str | None:
    direct_lanes = {"CDH6 / Ovarian ADC", "B7-H4 ADC", "Ovarian ADC"}
    direct_latest = sorted(_active_records([r for r in records if r.lane in direct_lanes]), key=lambda r: r.last_update or "", reverse=True)[:3]
    if not direct_latest:
        return None
    pieces = [f"{r.sponsor}: {_lane_label(r.lane)} {r.phase} ({r.nct_id})" for r in direct_latest]
    return "Recent direct oncology updates to recognize: " + "; ".join(pieces) + "."


def _investor_ammunition_read(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q2: adaptive implication fragments in plain language."""
    if cdh6_sig:
        anchor = cdh6_sig.phase3_sponsors[0] if cdh6_sig.phase3_sponsors else None
        if anchor and len(cdh6_sig.sponsors) >= 4:
            lead = f"Investor answer: {anchor} helps validate CDH6, but the broader sponsor spread means the CDH6 story is not closed."
        elif anchor:
            lead = f"Investor answer: {anchor} gives CDH6 clinical credibility, so the next question becomes what makes another CDH6 program different."
        else:
            lead = "Investor answer: CDH6 is still open, but the biology and patient fit have to be made obvious."
        context: list[str] = []
        if ovarian_sig:
            context.append("Use broad ovarian ADC activity to prove the category matters, not as the whole company story.")
        if b7h4_sig:
            context.append("Use B7-H4 as nearby attention, not as a substitute for CDH6.")
        return " ".join([lead] + context)
    if ovarian_sig:
        return "Investor answer: ovarian ADC activity helps category relevance, but it only becomes useful when tied to a clear target and patient group."
    if b7h4_sig:
        return "Investor answer: B7-H4 explains adjacent attention, but it should not carry the CDH6 story."
    return "No strong direct oncology investor-ammunition signal surfaced in this run."


def _metric_hits(records: list[TrialRecord], terms: list[str]) -> list[TrialRecord]:
    return _keyword_presence(records, terms)


def _count_records(records: list[TrialRecord], terms: list[str]) -> int:
    return len({r.nct_id for r in _metric_hits(records, terms)})


def _endpoint_number_read(records: list[TrialRecord]) -> str | None:
    """Quantified endpoint/protocol evidence without turning the summary into a table."""
    if not records:
        return None
    total = len({r.nct_id for r in records})
    metric_map = [
        ("ORR/response", ["objective response", "overall response", "orr", "response rate", "complete response", "partial response"]),
        ("PFS/time-to-event", ["progression-free", "pfs", "time to", "overall survival", "os"]),
        ("DOR/durability", ["duration of response", "dor", "durability", "durable"]),
        ("safety/tolerability", ["safety", "tolerability", "adverse event", "toxicity", "dose limiting", "maximum tolerated", "rp2d", "recommended phase 2"]),
    ]
    counts = [(label, _count_records(records, terms)) for label, terms in metric_map]
    visible = [(label, count) for label, count in counts if count > 0]
    if not visible:
        return None
    count_text = "; ".join(f"{label}: {count}/{total}" for label, count in visible)
    return f"Protocol endpoint intent visible in this pull: {count_text}."


def _selection_combo_number_read(records: list[TrialRecord]) -> str | None:
    if not records:
        return None
    total = len({r.nct_id for r in records})
    patient = _count_records(records, ["biomarker", "expression", "positive", "selected", "selection", "stratified", "molecular", "ihc", "overexpress", "platinum", "recurrent", "refractory", "resistant", "relapsed", "prior therapy"])
    combo = _count_records(records, ["combination", "combined", "pembrolizumab", "nivolumab", "paclitaxel", "carboplatin", "bevacizumab", "chemotherapy", " plus ", " with "])
    parts = []
    if patient:
        parts.append(f"patient-selection / treatment-context language: {patient}/{total}")
    if combo:
        parts.append(f"combination or partner-therapy language: {combo}/{total}")
    if not parts:
        return None
    return "Protocol design signals visible in this pull: " + "; ".join(parts) + "."


def _posted_result_records(records: list[TrialRecord]) -> list[TrialRecord]:
    return [r for r in records if r.observed_results and r.observed_results != "No posted result values surfaced"]


def _posted_results_read(records: list[TrialRecord]) -> str | None:
    posted = _posted_result_records(records)
    if not posted:
        return (
            "Observed-result check: no posted ORR/PFS/DOR/safety result values surfaced for this lane, "
            "so the current read should be treated as protocol-and-battlefield intelligence rather than an efficacy benchmark."
        )
    parts = []
    for r in posted[:4]:
        parts.append(f"{r.sponsor} ({r.nct_id}, {r.phase}): {r.observed_results}")
    return "Observed-result evidence surfaced: " + "; ".join(parts) + "."


def _proof_burden_read(sig: ClinicalLaneSignature | None) -> str | None:
    """Q2 support: assemble only the burdens actually visible in the data."""
    if sig is None:
        return None
    burdens: list[str] = []
    if sig.patient_selection_strength in {"prominent", "present"}:
        burdens.append("which patients should be CDH6-defined and why")
    if sig.combination_strength in {"prominent", "present"}:
        burdens.append("whether benefit is clear enough without getting lost inside combination therapy")
    if sig.safety_strength in {"prominent", "present"}:
        burdens.append("whether dosing and tolerability make real treatment use believable")
    if sig.response_strength in {"prominent", "present"}:
        burdens.append("whether response and durability are strong enough to matter")
    if not burdens:
        burdens.append("whether CDH6 can separate itself from broader ADC noise")
    if len(burdens) == 1:
        burden_text = burdens[0]
    else:
        burden_text = ", ".join(burdens[:-1]) + f", and {burdens[-1]}"
    return f"What investors will press on: {burden_text}."


def _lane_precision_note(sig: ClinicalLaneSignature) -> str:
    if sig.label.startswith("CDH6"):
        return "strict target lane"
    if "B7-H4" in sig.label:
        return "adjacent target lane"
    if "Broad ovarian ADC" in sig.label:
        return "category context lane, not target-specific proof"
    return "peripheral context lane"


def _trend_line(sig: ClinicalLaneSignature, role: str) -> str:
    """Q3: state trend + watch item, generated from the lane signature."""
    phase = _phase_role_fragment(sig)
    ownership = _ownership_state(sig)
    precision = _lane_precision_note(sig)
    if sig.label.startswith("CDH6"):
        watch = "Watch whether future CDH6 updates clarify patient selection better than the broader ovarian ADC field."
        if sig.combination_strength in {"prominent", "present"}:
            watch = "Watch whether CDH6 can show a clean role in treatment sequencing instead of being viewed only through combination logic."
        return f"CDH6 trend ({precision}): {phase}; {ownership}. {watch}"
    if "Broad ovarian ADC" in sig.label:
        return f"Broad ovarian ADC trend ({precision}): {phase}. The category is active, but broad ADC activity should be weighted below CDH6-specific evidence."
    if "B7-H4" in sig.label:
        return f"B7-H4 trend ({precision}): {phase}. This can pull attention toward gynecologic oncology, but it should stay separate from the CDH6 story."
    return f"{sig.label} ({precision}): {sig.strategic_state}. {_phase_role_fragment(sig)}."


def _positioning_line(cdh6_sig: ClinicalLaneSignature | None, ovarian_sig: ClinicalLaneSignature | None, b7h4_sig: ClinicalLaneSignature | None) -> str:
    """Q4: one adaptive positioning answer."""
    if cdh6_sig:
        anchor = cdh6_sig.phase3_sponsors[0] if cdh6_sig.phase3_sponsors else None
        if anchor and len(cdh6_sig.sponsors) >= 4:
            return (
                f"NXTC's cleanest position is not 'we are an ADC company.' It is: {anchor} validates CDH6, but no company has made the CDH6 story feel fully owned yet. "
                "The opening is to make CDH6 easy to understand around the right patients, target expression, tolerability, and evidence quality."
            )
        if anchor:
            return (
                f"NXTC should use {anchor}'s presence as proof that CDH6 deserves attention, then explain what makes its own CDH6 path different."
            )
        return "NXTC's cleanest position is CDH6 specificity: make the target, patient group, and evidence path easier to understand than the broad ADC backdrop."
    if ovarian_sig:
        return "NXTC should be judged against active ovarian ADC interest, but still needs a target-specific reason to stand apart."
    if b7h4_sig:
        return "B7-H4 helps explain nearby attention, but it should not replace the CDH6 positioning answer."
    return "The live clinical pull did not create a strong positioning change this run."

def _side_channel_read(records: list[TrialRecord]) -> str | None:
    parts: list[str] = []
    for lane in SIDE_LANE_ORDER:
        lane_recs = _lane_records(records, lane)
        if not lane_recs:
            continue
        sig = _derive_lane_signature(_lane_label(lane), lane_recs)
        if sig:
            parts.append(f"{sig.label}: {sig.strategic_state}; {sig.narrative_owner}")
    if not parts:
        return None
    return "Exploratory watch only: " + " | ".join(parts) + "."



def _sponsor_names_for_evidence(records: list[TrialRecord]) -> list[str]:
    """Pick sponsor names that deserve a sponsor-communications check.

    Prioritize direct oncology lanes and late-stage anchors. This is adaptive:
    if tomorrow's clinical pull surfaces different sponsors, the evidence layer
    checks those names instead of a fixed company list.
    """
    priority_lanes = {"CDH6 / Ovarian ADC", "B7-H4 ADC", "Ovarian ADC", "ADC Oncology"}
    ordered: list[str] = []
    for r in sorted(records, key=lambda rec: (0 if rec.lane in priority_lanes else 1, rec.phase, rec.sponsor)):
        if r.lane not in priority_lanes:
            continue
        if r.sponsor and r.sponsor not in ordered:
            ordered.append(r.sponsor)
    return ordered


def _evidence_item_fragment(item) -> str:
    year = f" {item.catalyst_year}" if getattr(item, "catalyst_year", None) else ""
    conf = getattr(item, "confidence", "limited")
    klass = getattr(item, "catalyst_class", "signal")
    stage = getattr(item, "data_stage", "UNKNOWN_STAGE")
    action = getattr(item, "evidence_action", "UNKNOWN_ACTION")
    stage_text = "" if stage == "UNKNOWN_STAGE" else f"; {stage}"
    action_text = "" if action == "UNKNOWN_ACTION" else f"; {action}"
    return f"{item.sponsor}: {item.title} [{klass}{year}{stage_text}{action_text}; {conf} confidence]"


def _sponsor_evidence_read(summary: SponsorEvidenceSummary | None) -> str | None:
    """Translate sponsor evidence into a freshness-aware executive fragment."""
    if summary is None:
        return None
    checked = ", ".join(summary.sponsors_checked[:10])
    audit = getattr(summary, "audit", None)
    audit_text = ""
    if audit is not None:
        universe = getattr(audit, "screened_sponsor_universe", max(audit.sponsors_discovered, audit.sponsors_searched))
        fast_screened = getattr(audit, "fast_screen_sponsors", 0)
        promoted = getattr(audit, "promoted_items", 0)
        parsed = getattr(audit, "deep_parsed_items", 0)
        unscreened = getattr(audit, "unscreened_sponsors", max(0, universe - fast_screened))
        priority_unscreened = tuple(getattr(audit, "unscreened_high_priority", ()) or ())
        focus_status = getattr(audit, "focus_company_screen_status", "")
        sponsor_grade_universe = getattr(audit, "sponsor_grade_universe", 0)
        deprioritized = getattr(audit, "non_sponsor_entities_deprioritized", 0)
        unscreened_note = ""
        if priority_unscreened:
            unscreened_note = f" Highest-priority unscreened sponsor-grade entities due to runtime budget: {', '.join(priority_unscreened[:5])}."
        focus_note = f" Focus-company screen status: {focus_status}." if focus_status else ""
        tier_note = ""
        if sponsor_grade_universe or deprioritized:
            tier_note = f" Sponsor-grade prioritization: {sponsor_grade_universe} company-like records prioritized; {deprioritized} institutional/site entities deprioritized."
        audit_text = (
            f" Evidence coverage: deep-searched {audit.mapped_sources_used} mapped/ticker sponsor handle(s), "
            f"fast-screened {fast_screened}/{max(universe, fast_screened, audit.sponsors_discovered)} strategic sponsor/entity records "
            f"({unscreened} not screened within the runtime budget), "
            f"promoted {promoted} evidence lead(s), parsed {parsed} item(s), "
            f"accepted {audit.accepted_items} active signal(s), and suppressed {audit.stale_items_removed} stale catalyst item(s). "
            f"Freshness model: publication date is evaluated separately from catalyst/event timing."
            + focus_note
            + tier_note
            + unscreened_note
        )

    if summary.result_items:
        top = summary.result_items[:3]
        pieces = [_evidence_item_fragment(item) for item in top]
        return (
            "Fresh sponsor evidence check found active result/safety language with monitored-lane overlap: "
            + "; ".join(pieces)
            + ". Treat media/news items as evidence leads until reconciled against sponsor releases, abstracts, and trial populations."
            + audit_text
        )
    if summary.timing_items:
        top = summary.timing_items[:3]
        pieces = [_evidence_item_fragment(item) for item in top]
        return (
            "Fresh sponsor evidence check found active data-timing or conference signals with monitored-lane overlap: "
            + "; ".join(pieces)
            + ". Stale conference headlines are suppressed so expired events do not masquerade as current catalysts."
            + audit_text
        )
    if getattr(summary, "stale_items", None):
        return (
            f"Sponsor evidence check searched dynamically discovered sponsors ({checked}) but only stale/expired catalyst language survived the first pass, so it was suppressed from the executive read."
            + audit_text
        )
    if summary.sponsors_checked:
        return (
            f"Sponsor evidence check did not surface current ORR/PFS/DOR/safety or active conference-timing language from dynamically discovered sponsors checked ({checked}). "
            "Current CDH6 read therefore remains protocol-and-battlefield intelligence, not sponsor-reported efficacy benchmarking."
            + audit_text
        )
    return "Sponsor evidence check did not have public-company/news handles for the surfaced sponsors in this run, but the dynamic sponsor registry still preserves sponsor names and evidence-search links for follow-up."


def _sponsor_evidence_trend(summary: SponsorEvidenceSummary | None) -> str | None:
    if summary is None:
        return None
    if summary.result_items:
        sponsors = ", ".join(dict.fromkeys(item.sponsor for item in summary.result_items[:4]))
        return f"Reported-data watch: fresh sponsor evidence surfaced outcome/safety language from {sponsors}; reconcile each signal against population, monotherapy/combination setting, endpoint definitions, and source quality."
    if summary.timing_items:
        sponsors = ", ".join(dict.fromkeys(item.sponsor for item in summary.timing_items[:4]))
        return f"Active-catalyst watch: fresh sponsor evidence surfaced conference or readout timing language from {sponsors}; future runs should track whether this converts into actual ORR/PFS/DOR/safety evidence."
    if getattr(summary, "stale_items", None):
        return "Freshness watch: stale conference/readout headlines were found and suppressed, which means the next improvement target is broader direct conference/IR routing rather than looser headline matching."
    return None


def _build_signals(records: list[TrialRecord], errors: list[str], sponsor_evidence: SponsorEvidenceSummary | None = None) -> list[ClinicalTrialSignal]:
    signals: list[ClinicalTrialSignal] = []
    if not records:
        detail = "ClinicalTrials.gov did not provide enough usable signal to support a clinical-landscape conclusion in this run."
        if errors:
            detail += " Source diagnostics were captured without interrupting the dashboard."
        return [ClinicalTrialSignal(
            bucket="new_information",
            title="Clinical source check",
            finding=detail,
            value="This prevents the dashboard from overstating external clinical intelligence when the source pull is degraded or empty.",
            evidence="; ".join(errors[:3]) if errors else "No matching records returned.",
            priority=99,
        )]

    cdh6_records = _lane_records(records, "CDH6 / Ovarian ADC")
    b7h4_records = _lane_records(records, "B7-H4 ADC")
    ovarian_records = _lane_records(records, "Ovarian ADC")
    adc_records = _lane_records(records, "ADC Oncology")
    side_records = [r for r in records if r.lane in SIDE_LANE_ORDER]

    cdh6_sig = _derive_lane_signature("CDH6 / ovarian ADC", cdh6_records)
    ovarian_sig = _derive_lane_signature("Broad ovarian ADC", ovarian_records)
    b7h4_sig = _derive_lane_signature("B7-H4 ADC", b7h4_records)
    signatures = [s for s in [cdh6_sig, ovarian_sig, b7h4_sig] if s is not None]
    signature_records = cdh6_records + ovarian_records + b7h4_records

    # Q1: What was found. One clean prioritized read plus direct oncology movement.

    if signatures:
        signals.append(ClinicalTrialSignal(
            bucket="new_information",
            title="Priority clinical edge signature",
            finding=_clinical_leverage_thesis(cdh6_sig, ovarian_sig, b7h4_sig),
            value="The clinical read is derived from combinations of phase anchors, sponsor structure, and protocol-language signals rather than any single raw field.",
            evidence=" | ".join(_signature_evidence(s) for s in signatures),
            priority=1,
        ))

    recent = _recent_movement_read(records)
    if recent:
        signals.append(ClinicalTrialSignal(
            bucket="new_information",
            title="Direct oncology movement",
            finding=recent,
            value="Only direct oncology movement is elevated here; exploratory updates remain supporting context unless they change the core thesis.",
            evidence="; ".join(f"{r.nct_id}: {r.sponsor} — {r.title}" for r in sorted(_active_records(records), key=lambda r: r.last_update or "", reverse=True)[:6]),
            priority=2,
        ))

    # Q2: Why it matters. Advance the meaning, do not restate Q1.
    if signatures:
        signals.append(ClinicalTrialSignal(
            bucket="value",
            title="Investor ammunition",
            finding=_investor_ammunition_read(cdh6_sig, ovarian_sig, b7h4_sig),
            value="Useful in board/investor conversations because it turns clinical structure into a defendable positioning answer.",
            evidence=" | ".join(_signature_evidence(s) for s in signatures),
            priority=3,
        ))

    evidence_records = cdh6_records or ovarian_records or b7h4_records
    evidence_label = "CDH6 / ovarian ADC" if cdh6_records else ("broad ovarian ADC" if ovarian_records else "B7-H4 ADC")
    evidence_pack = _clinical_evidence_pack_read(evidence_records, evidence_label)
    if evidence_pack:
        signals.append(ClinicalTrialSignal(
            bucket="value",
            title="Quantified clinical evidence pack",
            finding=evidence_pack,
            value="This keeps the executive read grounded in endpoint, patient-selection, combination, and posted-result evidence instead of pure interpretation.",
            evidence=_db_hook_evidence(evidence_records),
            priority=4,
        ))

    sponsor_read = _sponsor_evidence_read(sponsor_evidence)
    if sponsor_read:
        signals.append(ClinicalTrialSignal(
            bucket="value",
            title="Sponsor-reported evidence check",
            finding=sponsor_read,
            value="This separates what the registry says trials are designed to measure from whether sponsors have recently communicated actual clinical evidence or data timing.",
            evidence="; ".join(getattr(sponsor_evidence, "source_errors", ())[:3]) if sponsor_evidence else "Sponsor evidence layer not available.",
            priority=4,
        ))

    proof_sig = cdh6_sig or ovarian_sig or b7h4_sig
    proof_line = _proof_burden_read(proof_sig)
    if proof_line:
        signals.append(ClinicalTrialSignal(
            bucket="value",
            title="Clinical proof burden",
            finding=proof_line,
            value="Useful because it names what the program has to prove for the CDH6 story to earn distinct credit.",
            evidence=_signature_evidence(proof_sig),
            priority=5,
        ))

    # Q3: Trend. Keep lane states separated and confidence-weighted.
    for idx, line in enumerate(_trend_lines_from_signatures(signatures), start=5):
        signals.append(ClinicalTrialSignal(
            bucket="trend",
            title="Target-specific battlefield state",
            finding=line,
            value="Useful because the trend read keeps CDH6, broad ovarian ADC, and B7-H4 from blending into one generic ADC headline.",
            evidence=_db_hook_evidence(signature_records),
            priority=idx,
        ))

    if adc_records:
        adc_sig = _derive_lane_signature("Broader ADC oncology", adc_records)
        if adc_sig and adc_sig.priority_score >= 4:
            signals.append(ClinicalTrialSignal(
                bucket="trend",
                title="ADC category weather",
                finding=f"Broader ADC oncology remains modality context rather than the CDH6 thesis. The useful read is whether broad ADC appetite supports the category without pulling attention away from target-specific CDH6 positioning.",
                value="Broad ADC activity can support category attention, but it should not replace the target-specific CDH6 answer.",
                evidence=_signature_evidence(adc_sig),
                priority=8,
            ))

    side_line = _side_channel_read(side_records)
    if side_line:
        signals.append(ClinicalTrialSignal(
            bucket="trend",
            title="Exploratory watch discipline",
            finding=side_line,
            value="Optionality is visible, but the executive thesis remains anchored to CDH6 / ovarian ADC unless side-channel movement becomes strategically material.",
            evidence=_db_hook_evidence(side_records),
            priority=9,
        ))

    sponsor_trend = _sponsor_evidence_trend(sponsor_evidence)
    if sponsor_trend:
        signals.append(ClinicalTrialSignal(
            bucket="trend",
            title="Sponsor evidence trend",
            finding=sponsor_trend,
            value="Useful because sponsor communications can turn protocol intent into actual data timing or reported-evidence intelligence.",
            evidence="; ".join(item.title for item in getattr(sponsor_evidence, "items", ())[:4]) if sponsor_evidence else "No sponsor evidence items.",
            priority=9,
        ))

    # Q4: Positioning. One line that uses the inferred state, not another data recap.
    signals.append(ClinicalTrialSignal(
        bucket="positioning",
        title="NXTC positioning implication",
        finding=_positioning_line(cdh6_sig, ovarian_sig, b7h4_sig),
        value="This converts clinical-trial structure into a positioning answer rather than a sponsor list.",
        evidence=" | ".join(_signature_evidence(s) for s in signatures) if signatures else "ClinicalTrials.gov records are kept below the Executive Summary as supporting evidence.",
        priority=10,
    ))

    return sorted(signals, key=lambda s: s.priority)

def build_clinical_trials_intelligence() -> ClinicalTrialsSummary:
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    by_nct: dict[str, TrialRecord] = {}
    errors: list[str] = []
    audits: list[ClinicalTrialsDiscoveryAudit] = []

    for spec in CLINICAL_TRIAL_SEARCH_SPECS:
        records, audit = _fetch_spec(spec)
        audits.append(audit)
        if audit.error:
            errors.append(f"{spec.label} / {getattr(spec, 'query_family', 'unknown')}: {audit.error}")
        if audit.truncated:
            errors.append(
                f"{spec.label} / {getattr(spec, 'query_family', 'unknown')}: query reached bounded page cap "
                f"after {audit.fetched_pages} page(s); additional ClinicalTrials.gov records may exist upstream."
            )
        for record in records:
            existing = by_nct.get(record.nct_id)
            if existing is None:
                by_nct[record.nct_id] = record
            else:
                by_nct[record.nct_id] = _merge_duplicate_records(existing, record, spec)

    records = list(by_nct.values())
    records.sort(key=lambda r: (r.relevance_score, r.last_update or "", r.nct_id), reverse=True)
    discovered_sponsors = build_discovered_sponsor_registry(records)
    sponsor_evidence = build_sponsor_evidence_summary(_sponsor_names_for_evidence(records), discovered_sponsors=discovered_sponsors)
    signals = _build_signals(records, errors, sponsor_evidence)
    table = _trial_table(records)
    sponsor_table = sponsor_discovery_table(discovered_sponsors)
    audit_table = _discovery_audit_table(audits)
    payload = [asdict(record) | {"fetched_at_utc": fetched_at, "source": "clinicaltrials.gov"} for record in records]
    active_count = sum(1 for r in records if _is_active(r.status))
    source_status = "live" if records else ("degraded" if errors else "empty")

    return ClinicalTrialsSummary(
        source_status=source_status,
        fetched_at_utc=fetched_at,
        total_trials=len(records),
        active_trials=active_count,
        lanes_covered=sorted({r.lane for r in records}),
        signals=signals,
        trial_table=table,
        persistence_payload=payload,
        source_errors=errors,
        sponsor_evidence=sponsor_evidence,
        discovered_sponsors=discovered_sponsors,
        sponsor_discovery_table=sponsor_table,
        discovery_audit=audits,
        discovery_audit_table=audit_table,
    )
