from __future__ import annotations

import json
from unittest.mock import patch

from engines.clinical_trials_engine import build_clinical_trials_intelligence


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "B7-H4 ADC in Solid Tumors"},
                        "statusModule": {
                            "overallStatus": "Recruiting",
                            "startDateStruct": {"date": "2025-01"},
                            "lastUpdatePostDateStruct": {"date": "2026-05-01"},
                        },
                        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Example Bio"}},
                        "designModule": {"phases": ["PHASE1"]},
                        "conditionsModule": {"conditions": ["Ovarian Cancer"]},
                        "armsInterventionsModule": {"interventions": [{"name": "Example ADC"}]},
                    }
                }
            ]
        }).encode("utf-8")


@patch("engines.clinical_trials_engine.urlopen", return_value=_FakeResponse())
def test_clinical_trials_live_pull_contract(_mock_urlopen):
    summary = build_clinical_trials_intelligence()
    assert summary.total_trials == 1
    assert summary.active_trials == 1
    assert summary.source_status == "live"
    assert not summary.trial_table.empty
    assert summary.persistence_payload[0]["source"] == "clinicaltrials.gov"
    assert any(signal.bucket == "new_information" for signal in summary.signals)


@patch("engines.clinical_trials_engine.urlopen", return_value=_FakeResponse())
def test_clinical_trials_executive_language_avoids_dump_terms(_mock_urlopen):
    summary = build_clinical_trials_intelligence()
    executive_text = " ".join(signal.finding for signal in summary.signals)
    banned = [
        "returned records", "normalized records", "configured lanes", "+ more", "the new layer compares",
        "CDH6 answer", "Ovarian ADC answer", "B7-H4 answer", "active category context",
        "Core battlefield read", "Comparator read",
    ]
    assert not any(term in executive_text for term in banned)
    assert "ClinicalTrials.gov" not in executive_text or "ClinicalTrials.gov did not provide" in executive_text

class _FakeResultsResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT00000002", "briefTitle": "CDH6 ADC in Ovarian Cancer"},
                        "statusModule": {
                            "overallStatus": "Recruiting",
                            "startDateStruct": {"date": "2025-01"},
                            "lastUpdatePostDateStruct": {"date": "2026-05-01"},
                        },
                        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Daiichi Sankyo"}},
                        "designModule": {"phases": ["PHASE3"], "enrollmentInfo": {"count": 500}},
                        "conditionsModule": {"conditions": ["Platinum Resistant Ovarian Cancer"]},
                        "armsInterventionsModule": {"interventions": [{"name": "CDH6 ADC plus pembrolizumab"}]},
                        "outcomesModule": {
                            "primaryOutcomes": [{"measure": "Objective Response Rate (ORR)"}],
                            "secondaryOutcomes": [{"measure": "Progression-Free Survival (PFS)"}],
                        },
                        "eligibilityModule": {"eligibilityCriteria": "CDH6 expression positive biomarker selected recurrent platinum resistant ovarian cancer"},
                    },
                    "resultsSection": {
                        "outcomeMeasuresModule": {
                            "outcomeMeasures": [
                                {
                                    "title": "Objective Response Rate",
                                    "paramType": "Percentage",
                                    "unitOfMeasure": "%",
                                    "classes": [{"categories": [{"measurements": [{"value": "23"}]}]}],
                                }
                            ]
                        }
                    },
                }
            ]
        }).encode("utf-8")


@patch("engines.clinical_trials_engine.urlopen", return_value=_FakeResultsResponse())
def test_clinical_trials_surfaces_posted_result_values(_mock_urlopen):
    summary = build_clinical_trials_intelligence()
    executive_text = " ".join(signal.finding for signal in summary.signals)
    assert "Observed-result evidence surfaced" in executive_text
    assert "Objective Response Rate" in executive_text
    assert "23 %" in executive_text

from engines.sponsor_evidence_engine import build_sponsor_evidence_summary


def test_sponsor_evidence_layer_classifies_result_language(monkeypatch):
    def fake_news(_ticker):
        return [{
            "title": "Daiichi Sankyo reports updated ORR and safety data in ovarian ADC program at ASCO",
            "publisher": "Example Wire",
            "providerPublishTime": 1760000000,
            "link": "https://example.com/daiichi-orr-safety",
        }]

    monkeypatch.setattr("engines.sponsor_evidence_engine._news_items_for_ticker", fake_news)
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    summary = build_sponsor_evidence_summary(["Daiichi Sankyo"])
    assert summary.source_status == "live"
    assert summary.result_items
    assert summary.result_items[0].evidence_state == "reported_data_signal"
    assert "orr" in summary.result_items[0].matched_terms


def test_sponsor_evidence_layer_suppresses_unrelated_sponsor_news(monkeypatch):
    def fake_news(_ticker):
        return [{
            "title": "Inhibrx Biosciences INBRX-106 combo tops KEYTRUDA alone in Phase 2 cancer study",
            "publisher": "Example News",
            "providerPublishTime": 1760000000,
            "link": "https://example.com/unrelated-merck-keytruda",
        }]

    monkeypatch.setattr("engines.sponsor_evidence_engine._news_items_for_ticker", fake_news)
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    summary = build_sponsor_evidence_summary(["Merck Sharp & Dohme LLC"])
    assert summary.source_status == "empty"
    assert not summary.items

from engines.sponsor_discovery_engine import build_discovered_sponsor_registry, normalize_sponsor_name


def test_sponsor_discovery_normalizes_and_preserves_unmapped_entities():
    class R:
        nct_id = "NCTDISCOVERY01"
        title = "CDH6 ADC in ovarian cancer"
        sponsor = "Example Therapeutics, Inc."
        collaborators = "Academic Cancer Center, Daiichi Sankyo Co., Ltd."
        lane = "CDH6 / Ovarian ADC"
        phase = "PHASE2"
        status = "Recruiting"
        interventions = "DS-6000a ADC"
        conditions = "Ovarian Cancer"
        last_update = "2026-05-01"
        sponsor_type = "Biotech / emerging sponsor"

    registry = build_discovered_sponsor_registry([R()])
    names = [s.sponsor_name for s in registry]
    assert "Example" in names
    assert "Daiichi Sankyo" in names
    assert any("CDH6" in s.program_terms for s in registry)
    assert normalize_sponsor_name("Daiichi Sankyo Co., Ltd.") == "Daiichi Sankyo"


def test_clinical_trials_discovery_specs_are_sponsor_agnostic_and_recall_first():
    from config.clinical_trials_sources import CLINICAL_TRIAL_SEARCH_SPECS

    assert len(CLINICAL_TRIAL_SEARCH_SPECS) >= 10
    assert {"term", "intr", "titles", "cond"}.issubset({s.query_area for s in CLINICAL_TRIAL_SEARCH_SPECS})
    forbidden_sponsor_terms = ("NextCure", "Daiichi", "AstraZeneca", "Genmab", "Merck", "Lilly")
    assert not any(any(term in s.query for term in forbidden_sponsor_terms) for s in CLINICAL_TRIAL_SEARCH_SPECS)
    assert any("precision" in getattr(s, "query_family", "") for s in CLINICAL_TRIAL_SEARCH_SPECS)


@patch("engines.clinical_trials_engine.urlopen", return_value=_FakeResponse())
def test_clinical_trials_discovery_audit_is_preserved(_mock_urlopen):
    summary = build_clinical_trials_intelligence()
    assert summary.discovery_audit
    assert summary.discovery_audit_table is not None
    assert not summary.discovery_audit_table.empty
    assert "Query Family" in summary.discovery_audit_table.columns
    assert "Discovery Provenance" in summary.trial_table.columns


def test_sponsor_evidence_fast_screen_promotes_recent_press_release(monkeypatch):
    from engines.sponsor_evidence_engine import build_sponsor_evidence_summary
    from engines.sponsor_discovery_engine import DiscoveredSponsor

    def no_ticker_news(_ticker):
        return []

    def fake_fast_screen(source):
        if source.sponsor == "Example Oncology":
            return [{
                "title": "Example Oncology to present Phase 1 ovarian ADC data at ASCO 2026",
                "publisher": "GlobeNewswire",
                "providerPublishTime": "2026-05-01",
                "link": "https://example.com/example-oncology-asco-2026",
                "route": "fast_news_screen",
            }]
        return []

    discovered = [DiscoveredSponsor(
        sponsor_name="Example Oncology",
        normalized_name="Example Oncology",
        aliases=("Example Oncology, Inc.",),
        roles=("lead sponsor",),
        matched_lanes=("Ovarian ADC",),
        nct_ids=("NCTFAST01",),
        trial_count=1,
        phases=("PHASE1",),
        statuses=("Recruiting",),
        program_terms=("ovarian", "ADC"),
        conditions=("Ovarian Cancer",),
        sponsor_type="Biotech / emerging sponsor",
        last_update="2026-05-01",
        relevance_score=9,
        evidence_queries=(),
    )]

    monkeypatch.setattr("engines.sponsor_evidence_engine._news_items_for_ticker", no_ticker_news)
    monkeypatch.setattr("engines.sponsor_evidence_engine._fast_screen_news_items", fake_fast_screen)
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    summary = build_sponsor_evidence_summary([], discovered_sponsors=discovered)
    assert summary.source_status == "live"
    assert summary.timing_items or summary.result_items
    item = summary.items[0]
    assert item.evidence_route == "fast_news_screen"
    assert item.data_stage == "PHASE1"
    assert item.evidence_action == "PLANNED_PRESENTATION"
    assert summary.audit is not None
    assert summary.audit.fast_screen_sponsors >= 1
    assert summary.audit.promoted_items >= 1


def test_sponsor_evidence_fast_screen_suppresses_old_conference(monkeypatch):
    from engines.sponsor_evidence_engine import build_sponsor_evidence_summary
    from engines.sponsor_discovery_engine import DiscoveredSponsor

    def fake_fast_screen(_source):
        return [{
            "title": "Example Oncology to unveil preclinical B7-H4 ADC data at AACR 2024",
            "publisher": "Business Wire",
            "providerPublishTime": "2024-04-01",
            "link": "https://example.com/old-aacr-2024",
            "route": "fast_news_screen",
        }]

    discovered = [DiscoveredSponsor(
        sponsor_name="Example Oncology",
        normalized_name="Example Oncology",
        aliases=("Example Oncology, Inc.",),
        roles=("lead sponsor",),
        matched_lanes=("B7-H4 ADC",),
        nct_ids=("NCTFAST02",),
        trial_count=1,
        phases=("PHASE1",),
        statuses=("Recruiting",),
        program_terms=("B7-H4", "ADC"),
        conditions=("Solid Tumor",),
        sponsor_type="Biotech / emerging sponsor",
        last_update="2026-05-01",
        relevance_score=9,
        evidence_queries=(),
    )]

    monkeypatch.setattr("engines.sponsor_evidence_engine._fast_screen_news_items", fake_fast_screen)
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    summary = build_sponsor_evidence_summary([], discovered_sponsors=discovered)
    assert not summary.items
    assert summary.stale_items
    assert summary.audit is not None
    assert summary.audit.stale_items_removed >= 1


def test_precision_lane_config_removes_default_broad_adc_oncology_crawler():
    from config.clinical_trials_sources import CLINICAL_TRIAL_SEARCH_SPECS

    labels = {spec.label for spec in CLINICAL_TRIAL_SEARCH_SPECS}
    assert "ADC Oncology" not in labels
    ovarian_specs = [spec for spec in CLINICAL_TRIAL_SEARCH_SPECS if spec.label == "Ovarian ADC"]
    assert ovarian_specs
    assert all("precision" in spec.query_family for spec in ovarian_specs)
