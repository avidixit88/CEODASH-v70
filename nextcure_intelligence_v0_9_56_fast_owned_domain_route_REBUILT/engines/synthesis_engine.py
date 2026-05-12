"""Executive synthesis layer for v0.9.3.

This version is intentionally different from the Executive Summary. The summary
answers: "what is the current readout?" This engine answers: "what is new,
where is the edge, what is the gap, and what should be watched next?"

It derives second-order intelligence from the existing return table, channel
summaries, catalyst table, technical read, capital-flow read, and activation
state. No new data source is claimed in this build.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

import pandas as pd

from engines.activation_engine import ActivationSummary
from engines.alignment_engine import AlignmentSummary
from engines.capital_flow_engine import CapitalFlowSummary
from engines.catalyst_engine import CatalystSummary
from engines.channel_engine import ChannelSummary
from engines.classification_engine import ClassificationResult
from engines.market_regime_engine import MarketRegimeSummary
from engines.relative_performance_engine import safe_return
from engines.relevance_engine import StrategicRelevanceSummary
from engines.technical_engine import TechnicalSnapshot
from engines.window_score_engine import WindowScoreSummary


@dataclass(frozen=True)
class SynthesisSignal:
    label: str
    state: str
    meaning: str
    evidence: str
    implication: str
    priority: int


@dataclass(frozen=True)
class SynthesisSummary:
    headline: str
    thesis: str
    signal_cards: list[SynthesisSignal]
    what_changed: list[str]
    competitive_edges: list[str]
    interpretation_brief: list[str]
    patent_grant_watch: pd.DataFrame
    operating_recommendations: list[str]
    insight_delta_table: pd.DataFrame
    competitive_gap_table: pd.DataFrame
    trend_radar: list[str]
    next_questions: list[str]
    strategic_relevance: StrategicRelevanceSummary | None = None
    relevance_signal_table: pd.DataFrame | None = None
    relevance_theme_table: pd.DataFrame | None = None
    relevance_query_map: pd.DataFrame | None = None


def _fmt_pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):+.1f}%"


def _clean_number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None and not pd.isna(v)]
    return round(mean(clean), 2) if clean else None


def _state_from_spread(spread_5d: float | None, spread_30d: float | None) -> tuple[str, str]:
    s5 = 0.0 if spread_5d is None or pd.isna(spread_5d) else float(spread_5d)
    s30 = 0.0 if spread_30d is None or pd.isna(spread_30d) else float(spread_30d)
    if s5 > 3 and s30 > 0:
        return "Participating", "NXTC is being rewarded relative to the biotech benchmark across recent and medium-term windows."
    if s5 > 3 and s30 <= 0:
        return "Rebound Attempt", "NXTC is improving recently, but the move has not yet repaired the medium-term relative picture."
    if s5 < -3 and s30 < 0:
        return "Disconnected", "NXTC is not yet participating in the broader biotech/peer setup."
    if s30 < -5:
        return "Medium-Term Lag", "The short-term tape may be mixed, but the 30D relative posture still needs repair."
    return "Selective / Unconfirmed", "NXTC is not clearly breaking away from the sector yet."


def _build_insight_delta_table(return_table: pd.DataFrame, channel_summaries: list[ChannelSummary] | None) -> pd.DataFrame:
    """Create net-new intelligence: which lanes are improving, fading, or diverging from NXTC."""
    if return_table is None or return_table.empty or not channel_summaries:
        return pd.DataFrame()

    nxtc_5d = _clean_number(safe_return(return_table, "NXTC", "5D %"))
    nxtc_30d = _clean_number(safe_return(return_table, "NXTC", "30D %"))
    rows: list[dict[str, object]] = []

    for ch in channel_summaries:
        channel_5d = _clean_number(ch.avg_5d)
        channel_30d = _clean_number(ch.avg_30d)
        channel_90d = _clean_number(ch.avg_90d)
        slope = None if channel_5d is None or channel_30d is None else round(channel_5d - channel_30d, 2)
        nxtc_gap_5d = None if nxtc_5d is None or channel_5d is None else round(nxtc_5d - channel_5d, 2)
        nxtc_gap_30d = None if nxtc_30d is None or channel_30d is None else round(nxtc_30d - channel_30d, 2)

        if slope is None:
            signal = "Insufficient data"
            meaning = "The system cannot yet determine whether this lane is accelerating or fading."
        elif slope >= 5:
            signal = "Acceleration"
            meaning = "The lane is improving versus its 30D baseline, suggesting attention may be building."
        elif slope <= -5:
            signal = "Fade / cooling"
            meaning = "The lane is weaker now than its 30D baseline, suggesting attention may be cooling."
        elif channel_90d is not None and channel_90d >= 8 and (channel_5d or 0) < 0:
            signal = "Pullback inside strong quarter"
            meaning = "The lane was rewarded over the quarter, but recent weakness may represent digestion rather than abandonment."
        else:
            signal = "Stable / unclear"
            meaning = "The lane is not showing a strong directional change yet."

        if nxtc_gap_5d is not None:
            if nxtc_gap_5d <= -5:
                meaning += " NXTC is lagging this lane, which creates a perception gap to explain."
            elif nxtc_gap_5d >= 5:
                meaning += " NXTC is outperforming this lane, which may indicate company-specific attention."

        rows.append({
            "Lane": ch.label,
            "5D Lane Avg": channel_5d,
            "30D Lane Avg": channel_30d,
            "90D Lane Avg": channel_90d,
            "Lane Slope 5D-30D": slope,
            "NXTC Gap vs Lane 5D": nxtc_gap_5d,
            "NXTC Gap vs Lane 30D": nxtc_gap_30d,
            "Detected Signal": signal,
            "Meaning / Value": meaning,
            "Best Current Ticker": ch.best_ticker or "N/A",
            "Weakest Current Ticker": ch.worst_ticker or "N/A",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Abs Gap"] = df["NXTC Gap vs Lane 5D"].abs()
        df = df.sort_values(["Abs Gap", "Lane Slope 5D-30D"], ascending=[False, False], na_position="last").drop(columns=["Abs Gap"])
    return df.reset_index(drop=True)


def _build_competitive_gap_table(
    return_table: pd.DataFrame,
    catalyst_table: pd.DataFrame | None,
    channel_summaries: list[ChannelSummary] | None,
) -> pd.DataFrame:
    """Find where peer behavior may create a competitive signal instead of repeating the raw peer table."""
    if return_table is None or return_table.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    catalyst_tickers = set()
    if catalyst_table is not None and not catalyst_table.empty and "ticker" in catalyst_table.columns:
        catalyst_tickers = {str(x) for x in catalyst_table["ticker"].dropna().tolist()}

    channel_by_ticker: dict[str, list[str]] = {}
    for ch in channel_summaries or []:
        for ticker in ch.tickers:
            channel_by_ticker.setdefault(ticker, []).append(ch.label)

    nxtc_5d = _clean_number(safe_return(return_table, "NXTC", "5D %"))
    nxtc_30d = _clean_number(safe_return(return_table, "NXTC", "30D %"))

    for _, row in return_table.iterrows():
        ticker = str(row.get("Ticker", ""))
        if ticker in {"NXTC", "XBI", "QQQ", ""}:
            continue
        r5 = _clean_number(row.get("5D %"))
        r30 = _clean_number(row.get("30D %"))
        r90 = _clean_number(row.get("90D %"))
        if r5 is None and r30 is None:
            continue
        gap_5d = None if r5 is None or nxtc_5d is None else round(r5 - nxtc_5d, 2)
        gap_30d = None if r30 is None or nxtc_30d is None else round(r30 - nxtc_30d, 2)

        reason = []
        if gap_5d is not None and gap_5d >= 7:
            reason.append("peer is receiving near-term attention while NXTC lags")
        if gap_30d is not None and gap_30d >= 10:
            reason.append("medium-term perception gap is material")
        if ticker in catalyst_tickers:
            reason.append("peer has catalyst/read-through relevance")
        if r90 is not None and r90 >= 15 and (r5 or 0) < 0:
            reason.append("quarterly winner is pulling back, which may affect category sentiment")
        if not reason:
            continue

        strategic_question = "What is the market rewarding here that NXTC is not yet getting credit for?"
        if ticker in catalyst_tickers:
            strategic_question = "Is this peer shaping investor expectations for NXTC's catalyst lane?"
        elif gap_5d is not None and gap_5d >= 7:
            strategic_question = "Is this a messaging/visibility gap or a true scientific differentiation gap?"

        rows.append({
            "Ticker": ticker,
            "Channels": ", ".join(channel_by_ticker.get(ticker, ["General peer"])),
            "5D %": r5,
            "30D %": r30,
            "90D %": r90,
            "Gap vs NXTC 5D": gap_5d,
            "Gap vs NXTC 30D": gap_30d,
            "Why It Matters": "; ".join(reason),
            "Strategic Question": strategic_question,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Sort Gap"] = df["Gap vs NXTC 5D"].fillna(0).abs() + df["Gap vs NXTC 30D"].fillna(0).abs() * 0.35
        df = df.sort_values("Sort Gap", ascending=False).drop(columns=["Sort Gap"])
    return df.head(8).reset_index(drop=True)


def _build_trend_radar(insight_delta_table: pd.DataFrame, competitive_gap_table: pd.DataFrame) -> list[str]:
    radar: list[str] = []
    if insight_delta_table is not None and not insight_delta_table.empty:
        accel = insight_delta_table[insight_delta_table["Detected Signal"].astype(str).str.contains("Acceleration", case=False, na=False)]
        fades = insight_delta_table[insight_delta_table["Detected Signal"].astype(str).str.contains("Fade|cooling", case=False, na=False)]
        gaps = insight_delta_table.sort_values("NXTC Gap vs Lane 5D", ascending=True, na_position="last")
        if not accel.empty:
            row = accel.iloc[0]
            radar.append(f"Acceleration watch: {row['Lane']} is improving versus its 30D baseline. This is a lane-level trend, not just a ticker move.")
        if not fades.empty:
            row = fades.iloc[0]
            radar.append(f"Cooling watch: {row['Lane']} is fading versus its 30D baseline, which may reduce read-through support unless NXTC can create company-specific attention.")
        if not gaps.empty and pd.notna(gaps.iloc[0].get("NXTC Gap vs Lane 5D")) and float(gaps.iloc[0]["NXTC Gap vs Lane 5D"]) <= -5:
            row = gaps.iloc[0]
            radar.append(f"Perception gap watch: NXTC is lagging the {row['Lane']} lane by {_fmt_pct(row['NXTC Gap vs Lane 5D'])} over 5D. The CEO-level question is why that gap exists.")

    if competitive_gap_table is not None and not competitive_gap_table.empty:
        top = competitive_gap_table.iloc[0]
        radar.append(f"Competitive attention watch: {top['Ticker']} is the most notable peer signal in this run. {top['Strategic Question']}")

    if not radar:
        radar.append("No strong new lane-level trend was detected in this run. The correct executive read is to avoid forcing a conclusion and continue monitoring for confirmation.")
    return radar[:5]


def _edge_from_tables(
    insight_delta_table: pd.DataFrame,
    competitive_gap_table: pd.DataFrame,
    catalyst_summary: CatalystSummary | None,
    activation: ActivationSummary | None,
) -> list[str]:
    edges: list[str] = []

    if insight_delta_table is not None and not insight_delta_table.empty:
        # Keep short-term lane acceleration out of the executive edge bucket unless it creates a true
        # perception gap. The executive summary should prioritize clinical/narrative leverage over
        # trader-style lane momentum notes.
        lagging = insight_delta_table.sort_values("NXTC Gap vs Lane 5D", ascending=True, na_position="last")
        if not lagging.empty and pd.notna(lagging.iloc[0].get("NXTC Gap vs Lane 5D")) and float(lagging.iloc[0]["NXTC Gap vs Lane 5D"]) <= -5:
            row = lagging.iloc[0]
            edges.append(
                f"Messaging-gap edge: NXTC is underperforming the {row['Lane']} lane by {_fmt_pct(row['NXTC Gap vs Lane 5D'])} over 5D. That creates a concrete question for investor communication: what part of the category story is not being credited to NXTC?"
            )

    if competitive_gap_table is not None and not competitive_gap_table.empty:
        top = competitive_gap_table.iloc[0]
        edges.append(
            f"Peer read-through edge: {top['Ticker']} is creating the strongest competitive signal in this run because {str(top['Why It Matters']).lower()}."
        )

    if catalyst_summary and "pre" in catalyst_summary.primary_phase.lower():
        edges.append(
            "Catalyst-framing edge: the next analytical step is not just listing the catalyst, but tracking whether market behavior begins to validate the catalyst before the event."
        )
    if activation and "lag" in activation.activation_state.lower():
        edges.append(
            "Visibility edge: if catalyst proximity exists but market attention remains weak, the system should highlight that as a communications gap rather than only a stock-performance issue."
        )

    if not edges:
        edges.append("No decisive edge was detected. That itself is useful: the system should tell leadership when the evidence is not strong enough to justify action.")
    return edges[:5]


def _build_patent_grant_watch() -> pd.DataFrame:
    """Return no patent/grant rows until live ingestion exists.

    Earlier prototypes displayed roadmap placeholders. For the executive build,
    pseudo intelligence is intentionally removed: future patent and grant modules
    should populate this only after they perform real source ingestion.
    """
    return pd.DataFrame(columns=["Source", "Signal", "Synthesis Value", "Status"])



def build_synthesis_summary(
    *,
    return_table: pd.DataFrame,
    classification: ClassificationResult,
    market_regime: MarketRegimeSummary | None,
    window_score: WindowScoreSummary | None,
    capital_summary: CapitalFlowSummary | None,
    catalyst_summary: CatalystSummary | None,
    technical_snapshot: TechnicalSnapshot | None,
    alignment_summary: AlignmentSummary | None,
    activation_summary: ActivationSummary | None,
    channel_summaries: list[ChannelSummary] | None = None,
    catalyst_table: pd.DataFrame | None = None,
    strategic_relevance: StrategicRelevanceSummary | None = None,
    fresh_signals: list | None = None,
    **_ignored_future_inputs: object,
) -> SynthesisSummary:
    nxtc_5d = safe_return(return_table, "NXTC", "5D %")
    nxtc_30d = safe_return(return_table, "NXTC", "30D %")
    xbi_5d = safe_return(return_table, "XBI", "5D %")
    qqq_5d = safe_return(return_table, "QQQ", "5D %")
    spread_5d = classification.spread_5d_xbi
    spread_30d = getattr(classification, "spread_30d_xbi", None)

    participation_state, participation_meaning = _state_from_spread(spread_5d, spread_30d)
    setup_score = technical_snapshot.setup_score if technical_snapshot else 5.0
    window = window_score.score if window_score else 5.0
    activation_score = activation_summary.activation_score if activation_summary else 5.0

    insight_delta_table = _build_insight_delta_table(return_table, channel_summaries)
    competitive_gap_table = _build_competitive_gap_table(return_table, catalyst_table, channel_summaries)
    trend_radar = _build_trend_radar(insight_delta_table, competitive_gap_table)

    if competitive_gap_table is not None and not competitive_gap_table.empty:
        lead_peer = str(competitive_gap_table.iloc[0]["Ticker"])
        headline = f"The newest intelligence is the gap: {lead_peer} is producing a stronger peer signal than NXTC in this run."
    elif trend_radar and "Acceleration" in trend_radar[0]:
        headline = "The newest intelligence is lane acceleration: one monitored category is improving faster than its medium-term baseline."
    elif participation_state in {"Disconnected", "Medium-Term Lag"} and activation_score < 6.5:
        headline = "The newest intelligence is a perception gap: catalyst proximity is not yet translating into visible market attention."
    elif window >= 7 and setup_score >= 6:
        headline = "The newest intelligence is setup alignment: market window and technical posture are becoming more useful together."
    else:
        headline = "The newest intelligence is selective: the system sees signals, but no single edge is strong enough to overstate yet."

    thesis_parts = [
        participation_meaning,
        market_regime.combined_read if market_regime else classification.market_meaning,
    ]
    if trend_radar:
        thesis_parts.append(" ".join(trend_radar[:2]))
    thesis = " ".join(part for part in thesis_parts if part)

    relevance_card = None
    if strategic_relevance is not None:
        relevance_card = SynthesisSignal(
            label="Strategic Relevance",
            state="Personalized to NextCure",
            meaning=strategic_relevance.headline,
            evidence=f"{len(strategic_relevance.signal_table) if strategic_relevance.signal_table is not None else 0} relevance-scored signals; {len(strategic_relevance.theme_table) if strategic_relevance.theme_table is not None else 0} repeated themes.",
            implication="This is the relevance-filter layer: patents, grants, abstracts, PRs, and side-channel signals can be scored against what actually matters to NextCure before they reach the executive dashboard.",
            priority=0,
        )

    signal_cards = [
        SynthesisSignal(
            label="New Information Layer",
            state="Delta + Gap Detection",
            meaning="This section now identifies second-order changes: lane acceleration/fade, NXTC gaps versus relevant channels, and peer read-through signals.",
            evidence=f"Built from {len(channel_summaries or [])} channel baskets and {0 if competitive_gap_table is None else len(competitive_gap_table)} peer gap signals.",
            implication="This is intentionally different from the Executive Summary: it shows what changed or what gap appeared, not just the current dashboard readout.",
            priority=1,
        ),
        SynthesisSignal(
            label="Market Participation",
            state=participation_state,
            meaning=participation_meaning,
            evidence=f"NXTC 5D {_fmt_pct(nxtc_5d)} vs XBI {_fmt_pct(xbi_5d)}; spread {_fmt_pct(spread_5d)}.",
            implication="If participation does not improve, the next workstream should focus on why the market is not connecting the catalyst to valuation.",
            priority=2,
        ),
        SynthesisSignal(
            label="Competitive Read-Through",
            state="Active" if competitive_gap_table is not None and not competitive_gap_table.empty else "No major outlier",
            meaning=(
                f"Top detected peer signal: {competitive_gap_table.iloc[0]['Ticker']} — {competitive_gap_table.iloc[0]['Strategic Question']}"
                if competitive_gap_table is not None and not competitive_gap_table.empty
                else "No peer created a large enough gap to elevate as a competitive read-through signal."
            ),
            evidence=(
                f"{competitive_gap_table.iloc[0]['Ticker']} gap vs NXTC 5D: {_fmt_pct(competitive_gap_table.iloc[0]['Gap vs NXTC 5D'])}; 30D: {_fmt_pct(competitive_gap_table.iloc[0]['Gap vs NXTC 30D'])}."
                if competitive_gap_table is not None and not competitive_gap_table.empty
                else "Peer gaps below current alert threshold."
            ),
            implication="This gives leadership a clearer reason to ask what peers are being rewarded for and whether NXTC should counter-position, align, or ignore it.",
            priority=3,
        ),
        SynthesisSignal(
            label="Visibility / Attention",
            state=activation_summary.activation_state if activation_summary else "Unavailable",
            meaning=activation_summary.summary if activation_summary else "Activation layer unavailable.",
            evidence=f"Activation score {activation_score:.1f}/10; window score {window:.1f}/10.",
            implication="This converts market behavior into a communications hypothesis rather than only a trading readout.",
            priority=4,
        ),
    ]

    if relevance_card is not None:
        signal_cards.append(relevance_card)

    if fresh_signals:
        top_fresh = fresh_signals[0]
        signal_cards.append(SynthesisSignal(
            label="Fresh External Signal",
            state=getattr(top_fresh, "relevance", "Watch"),
            meaning=getattr(top_fresh, "signal", "Fresh external signal detected."),
            evidence=getattr(top_fresh, "category", "External intelligence"),
            implication=getattr(top_fresh, "implication", "Evaluate for relevance to NextCure strategy."),
            priority=0,
        ))

    what_changed = [
        f"NXTC recent movement: 5D {_fmt_pct(nxtc_5d)} and 30D {_fmt_pct(nxtc_30d)}. Read this against relevant peer and clinical lanes to separate a short-term bounce from a durable positioning repair.",
        f"Benchmark context: XBI 5D {_fmt_pct(xbi_5d)} and QQQ 5D {_fmt_pct(qqq_5d)}. This separates biotech pressure from general growth-market pressure.",
    ]
    what_changed.extend(trend_radar[:3])
    if fresh_signals:
        for fs in fresh_signals[:2]:
            what_changed.append(f"Fresh signal: {getattr(fs, 'category', 'External intelligence')} — {getattr(fs, 'signal', '')}")
    if strategic_relevance is not None:
        what_changed.extend(strategic_relevance.executive_brief[:2])

    competitive_edges = _edge_from_tables(insight_delta_table, competitive_gap_table, catalyst_summary, activation_summary)
    if strategic_relevance is not None:
        competitive_edges.extend([s.executive_takeaway for s in strategic_relevance.highest_priority_signals[:2]])

    interpretation_brief = [
        "The Interpretation Engine now prioritizes deltas, peer read-through, and clinical battlefield context rather than restating the same high-level narrative.",
        "The key read is where NXTC is being compared against active peer or clinical lanes without yet receiving the same level of market credit.",
        "Incoming information is filtered against NextCure targets, modalities, exploratory areas, and value drivers before it reaches the executive layer.",
    ]

    recommendations: list[str] = []
    if competitive_gap_table is not None and not competitive_gap_table.empty:
        top = competitive_gap_table.iloc[0]
        recommendations.append(f"Use {top['Ticker']} as the first competitive read-through case study: {top['Strategic Question']}")
    if insight_delta_table is not None and not insight_delta_table.empty:
        top_lane = insight_delta_table.iloc[0]
        recommendations.append(f"Track the {top_lane['Lane']} lane as this week's synthesis focus because it produced the largest NXTC/channel gap or slope signal.")
    if activation_summary and activation_summary.recommended_actions:
        recommendations.extend(activation_summary.recommended_actions[:1])
    if strategic_relevance is not None and strategic_relevance.next_questions:
        recommendations.append(f"Use the relevance map as this week's intake filter: {strategic_relevance.next_questions[0]}")

    next_questions = [
        "Which peer is the market rewarding this week, and is the reason scientifically relevant to NextCure or just broad-market noise?",
        "Is NXTC lagging a relevant lane because investors do not understand the story, because the catalyst is not trusted yet, or because the lane itself is weak?",
    ]
    if strategic_relevance is not None:
        next_questions.extend(strategic_relevance.next_questions[:4])

    seen = set()
    clean_recs = []
    for rec in recommendations:
        if rec not in seen:
            clean_recs.append(rec)
            seen.add(rec)

    return SynthesisSummary(
        headline=headline,
        thesis=thesis,
        signal_cards=sorted(signal_cards, key=lambda s: s.priority),
        what_changed=what_changed[:6],
        competitive_edges=competitive_edges,
        interpretation_brief=interpretation_brief,
        patent_grant_watch=_build_patent_grant_watch(),
        operating_recommendations=clean_recs[:5],
        insight_delta_table=insight_delta_table,
        competitive_gap_table=competitive_gap_table,
        trend_radar=trend_radar,
        next_questions=list(dict.fromkeys(next_questions)),
        strategic_relevance=strategic_relevance,
        relevance_signal_table=strategic_relevance.signal_table if strategic_relevance is not None else pd.DataFrame(),
        relevance_theme_table=strategic_relevance.theme_table if strategic_relevance is not None else pd.DataFrame(),
        relevance_query_map=strategic_relevance.query_map if strategic_relevance is not None else pd.DataFrame(),
    )
