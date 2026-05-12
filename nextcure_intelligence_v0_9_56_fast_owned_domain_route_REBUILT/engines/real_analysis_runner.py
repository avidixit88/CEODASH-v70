"""Iteration 4 orchestration: real data fetch + classification + channel insight layer."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.peer_channels import all_market_tickers, peer_metadata_by_ticker
from data.mock_market_data import (
    build_mock_insights,
    build_mock_kpi_cards,
    build_mock_peer_table,
    build_mock_performance,
    build_mock_technical_data,
)
from engines.capital_flow_engine import CapitalFlowSummary, build_capital_flow_insights, build_capital_flow_table, summarize_capital_flow
from engines.catalyst_engine import CatalystSummary, build_catalyst_intelligence_cards, build_catalyst_readout, catalyst_events_to_table, ingestion_backlog_table, summarize_catalysts
from engines.channel_engine import ChannelSummary, analyze_channels
from engines.classification_engine import ClassificationResult, classify_market_position
from engines.event_engine import build_event_reaction_insights, build_event_reaction_table
from engines.fresh_signal_engine import build_fresh_signals
from engines.clinical_trials_engine import ClinicalTrialsSummary, build_clinical_trials_intelligence
from engines.insight_engine import build_executive_insights, build_watch_items
from engines.market_data_engine import MarketDataBundle, add_technical_indicators, fetch_market_data
from engines.relative_performance_engine import build_relative_index, build_return_table, safe_return
from engines.market_regime_engine import MarketRegimeSummary, summarize_market_regime
from engines.window_score_engine import WindowScoreSummary, build_market_window_score
from engines.strategy_engine import StrategySummary, build_strategy_summary
from engines.scenario_engine import build_scenario_outlook
from engines.technical_engine import TechnicalSnapshot, analyze_ticker_technical, build_peer_technical_read, build_technical_table
from engines.catalyst_timing_engine import CatalystTimingSummary, build_catalyst_timing_summary
from engines.alignment_engine import AlignmentSummary, build_alignment_summary
from engines.activation_engine import ActivationSummary, build_activation_summary
from engines.synthesis_engine import SynthesisSummary, build_synthesis_summary
from engines.relevance_engine import StrategicRelevanceSummary, build_relevance_intelligence


@dataclass(frozen=True)
class AnalysisResults:
    performance: pd.DataFrame
    peer_table: pd.DataFrame
    technicals: dict[str, pd.DataFrame]
    kpis: list[dict[str, str]]
    insights: list[str]
    data_bundle: MarketDataBundle | None
    using_real_data: bool
    return_table: pd.DataFrame | None = None
    classification: ClassificationResult | None = None
    channel_summaries: list[ChannelSummary] | None = None
    channel_table: pd.DataFrame | None = None
    watch_items: list[dict[str, str]] | None = None
    catalyst_table: pd.DataFrame | None = None
    catalyst_summary: CatalystSummary | None = None
    catalyst_insights: list[str] | None = None
    ingestion_backlog: pd.DataFrame | None = None
    capital_flow_table: pd.DataFrame | None = None
    capital_flow_summary: CapitalFlowSummary | None = None
    capital_flow_insights: list[str] | None = None
    event_reaction_table: pd.DataFrame | None = None
    event_reaction_insights: list[str] | None = None
    catalyst_cards: list[dict[str, str]] | None = None
    market_regime: MarketRegimeSummary | None = None
    window_score: WindowScoreSummary | None = None
    strategy_summary: StrategySummary | None = None
    scenario_outlook: list[dict[str, str]] | None = None
    technical_snapshot: TechnicalSnapshot | None = None
    technical_table: pd.DataFrame | None = None
    peer_technical_read: list[str] | None = None
    catalyst_timing: CatalystTimingSummary | None = None
    alignment_summary: AlignmentSummary | None = None
    activation_summary: ActivationSummary | None = None
    synthesis_summary: SynthesisSummary | None = None
    strategic_relevance: StrategicRelevanceSummary | None = None
    fresh_signals: list | None = None
    clinical_trials: ClinicalTrialsSummary | None = None


def _format_delta(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    return f"{number:+.2f}%"


def _build_kpis(return_table: pd.DataFrame, failures: dict[str, str], classification: ClassificationResult) -> list[dict[str, str]]:
    nxtc_5d = safe_return(return_table, "NXTC", "5D %")
    xbi_5d = safe_return(return_table, "XBI", "5D %")
    qqq_5d = safe_return(return_table, "QQQ", "5D %")
    nxtc_30d = safe_return(return_table, "NXTC", "30D %")

    return [
        {"label": "NXTC 5D", "value": _format_delta(nxtc_5d), "caption": "Recent company movement"},
        {"label": "NXTC 30D", "value": _format_delta(nxtc_30d), "caption": "Medium-term posture"},
        {"label": "NXTC vs XBI", "value": _format_delta(classification.spread_5d_xbi), "caption": classification.nxtc_vs_xbi},
        {"label": "XBI 5D", "value": _format_delta(xbi_5d), "caption": "Biotech sector proxy"},
        {"label": "QQQ 5D", "value": _format_delta(qqq_5d), "caption": "Growth-market proxy"},
        {"label": "Data Gaps", "value": str(len(failures)), "caption": "Tickers safely skipped"},
    ]


def _build_peer_table(return_table: pd.DataFrame) -> pd.DataFrame:
    metadata = peer_metadata_by_ticker()
    rows: list[dict[str, object]] = []
    for _, row in return_table.iterrows():
        ticker = str(row["Ticker"])
        meta = metadata.get(ticker)
        if ticker in {"XBI", "QQQ"} or meta is None:
            continue
        rows.append({
            "Ticker": ticker,
            "Company": meta.company,
            "Channels": ", ".join(ch for ch in meta.channels if ch != "primary"),
            "Targets": ", ".join(meta.targets),
            "1D %": row.get("1D %"),
            "5D %": row.get("5D %"),
            "30D %": row.get("30D %"),
            "60D %": row.get("60D %"),
            "90D %": row.get("90D %"),
            "Read": meta.read_through,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("5D %", ascending=False, na_position="last").reset_index(drop=True)


def run_real_analysis() -> AnalysisResults:
    tickers = all_market_tickers()
    bundle = fetch_market_data(tickers, period="6mo", interval="1d", min_rows=30)

    required = {"NXTC", "XBI", "QQQ"}
    if not required.issubset(bundle.prices):
        strategic_relevance = build_relevance_intelligence()
        fresh_signals = build_fresh_signals()
        clinical_trials = build_clinical_trials_intelligence()
        return AnalysisResults(
            performance=build_mock_performance(),
            peer_table=build_mock_peer_table(),
            technicals=build_mock_technical_data(),
            kpis=build_mock_kpi_cards(),
            insights=[
                "Live market data was not available for all required benchmarks, so the app is showing prototype data while preserving the fresh-intelligence engine wiring.",
                "ClinicalTrials.gov intelligence remains available independently from Yahoo Finance, so external source analysis can still run even when market data falls back.",
                *build_mock_insights(),
            ],
            data_bundle=bundle,
            using_real_data=False,
            strategic_relevance=strategic_relevance,
            fresh_signals=fresh_signals,
            clinical_trials=clinical_trials,
        )

    technicals = {ticker: add_technical_indicators(df) for ticker, df in bundle.prices.items()}
    return_table = build_return_table(bundle.prices)
    performance = build_relative_index(bundle.prices, ["NXTC", "XBI", "QQQ"])
    peer_table = _build_peer_table(return_table)
    classification = classify_market_position(return_table)
    channel_summaries, channel_table = analyze_channels(return_table)
    capital_flow_table = build_capital_flow_table(channel_summaries)
    capital_flow_summary = summarize_capital_flow(channel_summaries, capital_flow_table)
    capital_flow_insights = build_capital_flow_insights(capital_flow_summary)

    catalyst_table = catalyst_events_to_table(return_table)
    catalyst_summary = summarize_catalysts(catalyst_table)
    catalyst_insights = build_catalyst_readout(catalyst_table, catalyst_summary)
    catalyst_cards = build_catalyst_intelligence_cards(catalyst_table, catalyst_summary)
    backlog = ingestion_backlog_table()

    event_reaction_table = build_event_reaction_table(catalyst_table, return_table)
    event_reaction_insights = build_event_reaction_insights(event_reaction_table)

    market_regime = summarize_market_regime(return_table, classification, capital_flow_summary)
    technical_table = build_technical_table(technicals)
    technical_snapshot = analyze_ticker_technical("NXTC", technicals["NXTC"]) if "NXTC" in technicals else None
    peer_technical_read = build_peer_technical_read(technical_table)
    catalyst_timing = build_catalyst_timing_summary(catalyst_table)
    window_score = build_market_window_score(return_table, classification, capital_flow_summary, market_regime, catalyst_summary.primary_phase)
    strategy_summary = build_strategy_summary(market_regime, window_score, classification, capital_flow_summary, catalyst_summary.primary_phase)
    scenario_outlook = build_scenario_outlook(market_regime, window_score, classification, capital_flow_summary)
    alignment_summary = build_alignment_summary(technical_snapshot, catalyst_timing, capital_flow_summary.adc_posture if capital_flow_summary else None)
    activation_summary = build_activation_summary(
        return_table=return_table,
        classification=classification,
        technical_snapshot=technical_snapshot,
        catalyst_phase=catalyst_summary.primary_phase,
        catalyst_positioning=catalyst_summary.primary_positioning,
        adc_posture=capital_flow_summary.adc_posture if capital_flow_summary else None,
        alignment_label=alignment_summary.label if alignment_summary else None,
    )
    strategic_relevance = build_relevance_intelligence()
    fresh_signals = build_fresh_signals()
    clinical_trials = build_clinical_trials_intelligence()
    synthesis_summary = build_synthesis_summary(
        return_table=return_table,
        classification=classification,
        market_regime=market_regime,
        window_score=window_score,
        capital_summary=capital_flow_summary,
        catalyst_summary=catalyst_summary,
        technical_snapshot=technical_snapshot,
        alignment_summary=alignment_summary,
        activation_summary=activation_summary,
        channel_summaries=channel_summaries,
        catalyst_table=catalyst_table,
        strategic_relevance=strategic_relevance,
    )

    insights = build_executive_insights(return_table, classification, channel_summaries, bundle.failures)
    activation_lines = [
        f"Market activation: {activation_summary.activation_state}. {activation_summary.summary}",
        f"What you can do: {activation_summary.recommended_actions[0] if activation_summary.recommended_actions else activation_summary.watch_signal}",
        f"Why it matters: {activation_summary.why_it_matters}",
        f"Activation watch: {activation_summary.watch_signal}",
    ]
    technical_lines = []
    if technical_snapshot:
        technical_lines.append(f"Technical setup: NXTC is {technical_snapshot.setup_state.lower()} ({technical_snapshot.setup_score:.1f}/10). {technical_snapshot.interpretation}")
    if alignment_summary:
        technical_lines.append(f"Technical + catalyst alignment: {alignment_summary.label}. {alignment_summary.what_it_means}")
    synthesis_lines = [
        f"Synthesis headline: {synthesis_summary.headline}",
        f"Interpretation thesis: {synthesis_summary.thesis}",
    ]
    insights = insights + synthesis_lines + activation_lines + [market_regime.combined_read, window_score.interpretation] + technical_lines + catalyst_insights[:3] + capital_flow_insights[:2] + event_reaction_insights[:1]
    watch_items = build_watch_items(classification, channel_summaries)
    watch_items.append({"label": "Window Score", "value": f"{window_score.score:.1f}/10", "caption": window_score.label})
    watch_items.append({"label": "Catalyst Phase", "value": catalyst_summary.primary_phase, "caption": catalyst_summary.primary_positioning})
    watch_items.append({"label": "Capital Flow", "value": capital_flow_summary.adc_posture, "caption": "ADC lane posture"})
    watch_items.append({"label": "Market Attention", "value": activation_summary.market_attention, "caption": activation_summary.activation_state})
    if technical_snapshot:
        watch_items.append({"label": "Technical Setup", "value": f"{technical_snapshot.setup_score:.1f}/10", "caption": technical_snapshot.setup_state})
    if alignment_summary:
        watch_items.append({"label": "Alignment", "value": alignment_summary.label, "caption": "Catalyst + technical read"})
    watch_items.append({"label": "Synthesis", "value": "Interpretation v1", "caption": synthesis_summary.headline})
    watch_items.append({"label": "Strategic Relevance", "value": "Personalized", "caption": strategic_relevance.headline})

    return AnalysisResults(
        performance=performance,
        peer_table=peer_table,
        technicals=technicals,
        kpis=_build_kpis(return_table, bundle.failures, classification),
        insights=insights,
        data_bundle=bundle,
        using_real_data=True,
        return_table=return_table,
        classification=classification,
        channel_summaries=channel_summaries,
        channel_table=channel_table,
        watch_items=watch_items,
        catalyst_table=catalyst_table,
        catalyst_summary=catalyst_summary,
        catalyst_insights=catalyst_insights,
        ingestion_backlog=backlog,
        capital_flow_table=capital_flow_table,
        capital_flow_summary=capital_flow_summary,
        capital_flow_insights=capital_flow_insights,
        event_reaction_table=event_reaction_table,
        event_reaction_insights=event_reaction_insights,
        catalyst_cards=catalyst_cards,
        market_regime=market_regime,
        window_score=window_score,
        strategy_summary=strategy_summary,
        scenario_outlook=scenario_outlook,
        technical_snapshot=technical_snapshot,
        technical_table=technical_table,
        peer_technical_read=peer_technical_read,
        catalyst_timing=catalyst_timing,
        alignment_summary=alignment_summary,
        activation_summary=activation_summary,
        synthesis_summary=synthesis_summary,
        strategic_relevance=strategic_relevance,
        fresh_signals=fresh_signals,
        clinical_trials=clinical_trials,
    )
