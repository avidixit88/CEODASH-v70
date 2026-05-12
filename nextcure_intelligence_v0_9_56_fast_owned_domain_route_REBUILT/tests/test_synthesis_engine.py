import pandas as pd

from engines.activation_engine import build_activation_summary
from engines.capital_flow_engine import build_capital_flow_table, summarize_capital_flow
from engines.catalyst_engine import catalyst_events_to_table, summarize_catalysts
from engines.channel_engine import analyze_channels
from engines.classification_engine import classify_market_position
from engines.market_regime_engine import summarize_market_regime
from engines.synthesis_engine import build_synthesis_summary
from engines.window_score_engine import build_market_window_score


def test_synthesis_engine_builds_interpretation_payload():
    return_table = pd.DataFrame([
        {"Ticker": "NXTC", "1D %": 0.2, "5D %": -4.0, "30D %": -12.0, "60D %": -14.0, "90D %": -18.0},
        {"Ticker": "XBI", "1D %": 0.1, "5D %": 1.0, "30D %": -1.0, "60D %": 2.0, "90D %": 4.0},
        {"Ticker": "QQQ", "1D %": 0.3, "5D %": 2.0, "30D %": 4.0, "60D %": 7.0, "90D %": 10.0},
        {"Ticker": "ADCT", "1D %": 0.0, "5D %": 5.5, "30D %": 8.0, "60D %": 12.0, "90D %": 20.0},
        {"Ticker": "ZYME", "1D %": 0.0, "5D %": 4.5, "30D %": 6.0, "60D %": 8.0, "90D %": 11.0},
    ])
    classification = classify_market_position(return_table)
    channels, channel_table = analyze_channels(return_table)
    capital_table = build_capital_flow_table(channels)
    capital_summary = summarize_capital_flow(channels, capital_table)
    catalyst_table = catalyst_events_to_table(return_table)
    catalyst_summary = summarize_catalysts(catalyst_table)
    market_regime = summarize_market_regime(return_table, classification, capital_summary)
    window_score = build_market_window_score(return_table, classification, capital_summary, market_regime, catalyst_summary.primary_phase)
    activation = build_activation_summary(
        return_table=return_table,
        classification=classification,
        technical_snapshot=None,
        catalyst_phase=catalyst_summary.primary_phase,
        catalyst_positioning=catalyst_summary.primary_positioning,
        adc_posture=capital_summary.adc_posture,
        alignment_label=None,
    )
    synthesis = build_synthesis_summary(
        return_table=return_table,
        classification=classification,
        market_regime=market_regime,
        window_score=window_score,
        capital_summary=capital_summary,
        catalyst_summary=catalyst_summary,
        technical_snapshot=None,
        alignment_summary=None,
        activation_summary=activation,
        channel_summaries=channels,
        catalyst_table=catalyst_table,
    )
    assert synthesis.headline
    assert len(synthesis.signal_cards) == 4
    assert synthesis.patent_grant_watch.empty
    assert not synthesis.insight_delta_table.empty
    assert "Meaning / Value" in synthesis.insight_delta_table.columns
    assert synthesis.trend_radar
    assert synthesis.next_questions


def test_sponsor_evidence_suppresses_expired_conference_year(monkeypatch):
    from engines.sponsor_evidence_engine import build_sponsor_evidence_summary

    def fake_news(_ticker):
        return [{
            "title": "NextCure and LCB to unveil promising preclinical B7-H4 ADC data at AACR 2024",
            "publisher": "Example Wire",
            "providerPublishTime": 1712000000,
            "link": "https://example.com/nxtc-aacr-2024",
        }]

    monkeypatch.setattr("engines.sponsor_evidence_engine._news_items_for_ticker", fake_news)
    monkeypatch.setattr("engines.sponsor_evidence_engine._fast_screen_news_items", lambda _source: [])
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    monkeypatch.setattr("engines.sponsor_evidence_engine._discover_company_evidence_candidate_urls", lambda _source: [])
    summary = build_sponsor_evidence_summary(["NextCure"])
    assert summary.source_status == "stale_only"
    assert not summary.timing_items
    assert summary.stale_items
    assert summary.audit is not None
    assert summary.audit.stale_items_removed >= 1


def test_sponsor_evidence_keeps_current_year_asco_catalyst(monkeypatch):
    from engines.sponsor_evidence_engine import build_sponsor_evidence_summary

    def fake_news(_ticker):
        return [{
            "title": "NextCure to present SIM0505 ovarian ADC clinical data at ASCO 2026",
            "publisher": "Example Wire",
            "providerPublishTime": 1779000000,
            "link": "https://example.com/nxtc-asco-2026",
        }]

    monkeypatch.setattr("engines.sponsor_evidence_engine._news_items_for_ticker", fake_news)
    monkeypatch.setattr("engines.sponsor_evidence_engine._fast_screen_news_items", lambda _source: [])
    monkeypatch.setattr("engines.sponsor_evidence_engine._ir_newsroom_screen_items", lambda _source: [])
    monkeypatch.setattr("engines.sponsor_evidence_engine._discover_company_evidence_candidate_urls", lambda _source: [])
    summary = build_sponsor_evidence_summary(["NextCure"])
    assert summary.source_status == "live"
    assert summary.timing_items or summary.result_items
    assert summary.items[0].freshness_state == "upcoming_catalyst"
    assert summary.items[0].catalyst_year == 2026
