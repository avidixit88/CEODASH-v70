"""NextCure Intelligence System - v0.9.47 evidence route fallback build.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from engines.prototype_runner import run_prototype_analysis
from engines.sponsor_evidence_engine import sponsor_evidence_table, sponsor_evidence_audit_table, sponsor_evidence_trace_table, stale_sponsor_evidence_table
from ui.charts import capital_flow_chart, catalyst_priority_chart, channel_momentum_chart, peer_bar_chart, peer_timeframe_comparison_chart, relative_performance_chart, technical_stock_chart, technical_setup_chart
from ui.layout import render_hero, render_insights, render_kpi_cards, render_watch_items, render_dashboard_nav, render_synthesis_summary, render_premium_executive_summary, render_buildwell_emblem
from ui.styles import inject_global_styles

st.set_page_config(
    page_title="NextCure Intelligence System",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_global_styles()

if "analysis_started" not in st.session_state:
    st.session_state.analysis_started = False
if "results" not in st.session_state:
    st.session_state.results = None
if "selected_technical_ticker" not in st.session_state:
    st.session_state.selected_technical_ticker = "NXTC"


def render_nextcure_debug_trace(results, *, expanded: bool = True) -> None:
    """Render the NextCure/SIM0505 evidence trace visibly.

    This is deliberately observational: it does not add NextCure to ClinicalTrials.gov
    queries or force any evidence into the executive summary. It only exposes the
    path the current run took so we can debug discovery, routing, parsing, and
    promotion decisions.
    """
    clinical = getattr(results, "clinical_trials", None)
    sponsor_evidence = getattr(clinical, "sponsor_evidence", None) if clinical is not None else None

    st.markdown("### 🧪 Debug Trace: NextCure Evidence Path")
    st.caption(
        "Debug-only panel for v0.9.47. This trace is observational only: it does not hardcode "
        "NextCure into ClinicalTrials.gov discovery or force evidence acceptance. It shows whether "
        "NextCure/SIM0505 surfaced naturally, where it entered the evidence universe, and why any "
        "candidate evidence was accepted or rejected."
    )

    if clinical is None:
        st.warning("ClinicalTrials.gov results object is not present for this run yet.")
        return
    if sponsor_evidence is None:
        st.warning("Sponsor evidence summary is not present for this run yet.")
        return

    trace_df = sponsor_evidence_trace_table(sponsor_evidence)
    audit_df = sponsor_evidence_audit_table(sponsor_evidence)

    with st.expander("🧪 Debug Trace: NextCure ClinicalTrials.gov + Evidence Routing", expanded=expanded):
        if trace_df.empty:
            st.warning(
                "Trace table is empty. That means the debug trace object was not attached to the sponsor "
                "evidence summary, which is itself a wiring issue to fix."
            )
        else:
            st.dataframe(trace_df, use_container_width=True, hide_index=True)

        if not audit_df.empty:
            st.markdown("#### Evidence routing audit for this run")
            st.dataframe(audit_df, use_container_width=True, hide_index=True)

        st.caption(
            "Interpretation guide: if ClinicalTrials.gov discovered focus sponsor/program = NO, the failure is "
            "upstream in lane query or NCT payload extraction. If it is YES but raw titles are empty, the failure "
            "is page/source discovery or parsing. If raw titles exist but promoted/accepted titles are empty, the "
            "failure is promotion, freshness, or lane-relevance classification."
        )

header_left, header_center, header_right = st.columns([0.08, 0.84, 0.08])
with header_center:
    render_hero()
    st.markdown('<div class="hero-button-shell">', unsafe_allow_html=True)
    cta_left, cta_mid, cta_right = st.columns([0.34, 0.32, 0.34])
    with cta_mid:
        start_clicked = st.button("START ANALYSIS", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if start_clicked:
    st.session_state.analysis_started = True
    st.session_state.active_page = "Executive Summary"
    st.session_state.dashboard_jump_to = "Executive Summary"
    progress = st.progress(0, text="Initializing market positioning layer...")
    steps = [
        "Comparing NXTC to XBI and QQQ...",
        "Constructing peer landscape...",
        "Calculating relative performance...",
        "Building six-month technical charts...",
        "Applying RSI and MACD overlays...",
        "Classifying 30D / 60D / Quarterly 90D trend posture...",
        "Analyzing peer and ADC capital-flow channels...",
        "Mapping catalyst and capital-flow intelligence...",
        "Scoring market window and regime quality...",
        "Building strategy and scenario outlook...",
        "Scoring NextCure-specific relevance map...",
        "Pulling live ClinicalTrials.gov intelligence...",
        "Compressing external signals into the four executive buckets...",
        "Generating executive readout...",
    ]
    for idx, step in enumerate(steps, start=1):
        time.sleep(0.22)
        progress.progress(idx / len(steps), text=step)
    st.session_state.results = run_prototype_analysis()
    progress.empty()
    st.rerun()

if st.session_state.analysis_started and st.session_state.results is not None:
    results = st.session_state.results

    pages = [
        "Executive Summary",
        "Interpretation Engine",
        "Fresh Intelligence",
        "Stock Technicals",
        "Peer Landscape",
        "Channel Intelligence",
        "Catalyst & Capital",
        "Technical + Catalyst",
        "Strategy & Timing",
        "Market Rhythm",
    ]
    if "active_page" not in st.session_state or st.session_state.active_page not in pages:
        st.session_state.active_page = "Executive Summary"

    active_page = render_dashboard_nav(pages, st.session_state.active_page)


    if active_page == "Fresh Intelligence":
        st.markdown("## Fresh Intelligence Layer")
        st.caption("External strategic signals synthesized into NextCure-specific relevance. ClinicalTrials.gov now runs recall-first sponsor-agnostic discovery, query-family audit trails, sponsor extraction, and evidence routing on each analysis run; raw detail stays as drill-down evidence, not executive clutter.")

        clinical = getattr(results, "clinical_trials", None)
        if clinical is not None:
            st.markdown("### ClinicalTrials.gov Live Intelligence")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Source", str(getattr(clinical, "source_status", "unknown")).title())
            with c2:
                st.metric("Signals", int(getattr(clinical, "total_trials", 0) or 0))
            with c3:
                st.metric("Active", int(getattr(clinical, "active_trials", 0) or 0))
            with c4:
                st.metric("Lanes", len(getattr(clinical, "lanes_covered", []) or []))

            for signal in getattr(clinical, "signals", []) or []:
                with st.container(border=True):
                    st.markdown(f"#### {signal.title}")
                    st.markdown(f"**Finding:** {signal.finding}")
                    st.markdown(f"**Value:** {signal.value}")
                    st.caption(f"Evidence: {signal.evidence}")

            sponsor_table = getattr(clinical, "sponsor_discovery_table", None)
            if sponsor_table is not None and not sponsor_table.empty:
                with st.expander("Dynamically discovered sponsors from ClinicalTrials.gov"):
                    st.caption("This table is generated from the live registry pull. Static ticker mappings enrich sponsors only after discovery; they do not control which sponsors appear.")
                    st.dataframe(sponsor_table, use_container_width=True, hide_index=True)

            sponsor_evidence = getattr(clinical, "sponsor_evidence", None)
            if sponsor_evidence is not None:
                evidence_df = sponsor_evidence_table(sponsor_evidence)
                evidence_audit_df = sponsor_evidence_audit_table(sponsor_evidence)
                evidence_trace_df = sponsor_evidence_trace_table(sponsor_evidence)
                stale_df = stale_sponsor_evidence_table(sponsor_evidence)
                if not evidence_df.empty:
                    with st.expander("Sponsor catalyst intelligence: fresh evidence signals"):
                        st.caption("Freshness-aware evidence only. Stale conference items are suppressed from the executive summary and shown separately for audit.")
                        st.dataframe(evidence_df, use_container_width=True, hide_index=True)
                else:
                    unmapped = list(getattr(sponsor_evidence, "unmapped_sponsors", []) or [])
                    if unmapped:
                        st.caption("Sponsor evidence layer discovered sponsors without mapped public-company/news handles yet: " + ", ".join(unmapped[:8]) + ". They remain in the discovery registry for follow-up evidence routing.")
                    else:
                        st.caption("Sponsor evidence layer ran, but no current sponsor communication matched clinical result, endpoint, or active data-timing language in this run.")
                if not evidence_audit_df.empty:
                    with st.expander("Sponsor evidence audit: coverage, stale suppression, and routing"):
                        st.dataframe(evidence_audit_df, use_container_width=True, hide_index=True)
                if not evidence_trace_df.empty:
                    with st.expander("🧪 Debug Trace: NextCure ClinicalTrials.gov + Evidence Routing", expanded=True):
                        st.caption("Debug-only trace for this run. This distinguishes whether NextCure/SIM0505 came from ClinicalTrials.gov itself versus mapped evidence enrichment, and shows where the evidence parser promoted or rejected candidate releases.")
                        st.dataframe(evidence_trace_df, use_container_width=True, hide_index=True)
                if not stale_df.empty:
                    with st.expander("Suppressed stale catalyst evidence"):
                        st.caption("These items matched lane/catalyst terms but were not allowed into the executive read because their timing is stale or expired.")
                        st.dataframe(stale_df, use_container_width=True, hide_index=True)


            audit_table = getattr(clinical, "discovery_audit_table", None)
            if audit_table is not None and not audit_table.empty:
                with st.expander("ClinicalTrials.gov discovery audit: query families and recall checks"):
                    st.caption("This audit proves which sponsor-agnostic query families ran, how many records were fetched, how many were retained after relevance filtering, and whether a query hit the bounded page cap.")
                    st.dataframe(audit_table, use_container_width=True, hide_index=True)

            trial_table = getattr(clinical, "trial_table", None)
            if trial_table is not None and not trial_table.empty:
                with st.expander("ClinicalTrials.gov supporting study detail from this run"):
                    st.dataframe(trial_table, use_container_width=True, hide_index=True)

            errors = list(getattr(clinical, "source_errors", []) or [])
            if sponsor_evidence is not None:
                errors.extend(list(getattr(sponsor_evidence, "source_errors", []) or []))
            if errors:
                with st.expander("ClinicalTrials.gov source diagnostics"):
                    for err in errors:
                        st.caption(err)


    if active_page == "Executive Summary":
        if getattr(results, "using_real_data", False):
            st.markdown('<div class="exec-data-note-wrap"><div class="exec-data-note good"><span class="data-dot"></span>Live market data active for this run.</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="exec-data-note-wrap"><div class="exec-data-note warn"><span class="data-dot"></span>Prototype fallback data is showing because live benchmark data was unavailable.</div></div>', unsafe_allow_html=True)
        render_premium_executive_summary(results)
        st.markdown("---")
        render_nextcure_debug_trace(results, expanded=True)


    if active_page == "Interpretation Engine":
        st.markdown('<div class="section-title">Data → Meaning → Value</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                This layer separates interpretation from the executive summary and focuses on deltas, perception gaps, competitive read-through, and live ClinicalTrials.gov intelligence.
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_synthesis_summary(getattr(results, "synthesis_summary", None))

    if active_page == "Stock Technicals":
        st.markdown('<div class="section-title">Six-Month Stock Technicals</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                CEO-facing technical view: actual price structure first, then RSI and MACD underneath. These are not exposed as system toggles;
                the backend decides the standard six-month lookback and indicator stack.
            </div>
            """,
            unsafe_allow_html=True,
        )
        priority_order = ["NXTC", "XBI", "QQQ", "GSK", "MRK", "DSNKY", "AZN", "GILD", "GMAB", "ZYME", "DAWN", "ADCT"]
        tickers = [t for t in priority_order if t in results.technicals]
        if st.session_state.selected_technical_ticker not in results.technicals:
            st.session_state.selected_technical_ticker = "NXTC" if "NXTC" in results.technicals else tickers[0]

        for start in range(0, len(tickers), 4):
            cols = st.columns(4)
            for col, ticker in zip(cols, tickers[start:start + 4]):
                df = results.technicals[ticker]
                latest_close = df["Close"].iloc[-1]
                latest_rsi = df["RSI14"].iloc[-1]
                with col:
                    if st.button(f"{ticker}", key=f"ticker_{ticker}"):
                        st.session_state.selected_technical_ticker = ticker
                    st.markdown(
                        f"""
                        <div class="ticker-card">
                            <div class="ticker-symbol">{ticker}</div>
                            <div class="ticker-read">Close {latest_close:.2f} · RSI {latest_rsi:.0f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        selected = st.session_state.selected_technical_ticker
        tech_table = getattr(results, "technical_table", None)
        if tech_table is not None and not tech_table.empty and selected in tech_table["Ticker"].values:
            row = tech_table[tech_table["Ticker"] == selected].iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="card"><div class="metric-label">Setup Score</div><div class="metric-value">{float(row["Setup Score"]):.1f}/10</div><div class="muted">{row["Setup State"]}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="card"><div class="metric-label">Trend</div><div class="metric-value" style="font-size:1rem;">{row["Trend"]}</div><div class="muted">Price structure</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="card"><div class="metric-label">Momentum</div><div class="metric-value" style="font-size:1rem;">{row["Momentum"]}</div><div class="muted">RSI + MACD</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="card"><div class="metric-label">Accumulation</div><div class="metric-value" style="font-size:1rem;">{row["Accumulation"]}</div><div class="muted">Volume behavior</div></div>', unsafe_allow_html=True)
        st.plotly_chart(technical_stock_chart(results.technicals[selected], selected), use_container_width=True)

    if active_page == "Peer Landscape":
        st.markdown('<div class="section-title">Peer Landscape</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="executive-narrative">
                <div class="summary-title">What this section is telling us</div>
                <div class="summary-body">
                    This page compares NXTC against the companies that can influence investor perception around its story:
                    direct ADC read-through names, ovarian cancer names, and broader oncology capital-flow comparables.
                    The chart now shows 5D, 30D, and 90D returns side-by-side so leadership can quickly separate a short-term move
                    from a real quarterly trend.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if getattr(results, "using_real_data", False):
            st.markdown(
                """
                <div class="muted" style="margin-bottom: .85rem;">
                    Real six-month market data is feeding this view. Missing tickers are skipped safely on the backend.
                </div>
                """,
                unsafe_allow_html=True,
            )
        if results.peer_table.empty:
            st.info("Peer table is unavailable because no peer market data returned usable history.")
        else:
            peer_df = results.peer_table.copy()
            # CEO-facing summary cards before the chart.
            def _fmt_pct(value):
                try:
                    return f"{float(value):+.1f}%"
                except Exception:
                    return "N/A"
            strongest_5d = peer_df.sort_values("5D %", ascending=False, na_position="last").iloc[0]
            strongest_90d = peer_df.sort_values("90D %", ascending=False, na_position="last").iloc[0]
            weakest_5d = peer_df.sort_values("5D %", ascending=True, na_position="last").iloc[0]
            nxtc_row = peer_df[peer_df["Ticker"] == "NXTC"]
            nxtc_caption = "Primary company"
            if not nxtc_row.empty:
                nr = nxtc_row.iloc[0]
                nxtc_caption = f"5D {_fmt_pct(nr.get('5D %'))} · 30D {_fmt_pct(nr.get('30D %'))} · 90D {_fmt_pct(nr.get('90D %'))}"
            summary_cards = [
                ("NXTC read", "Primary benchmark", nxtc_caption),
                ("Strongest 5D", str(strongest_5d["Ticker"]), f"{strongest_5d['Company']} · {_fmt_pct(strongest_5d.get('5D %'))}"),
                ("Strongest 90D", str(strongest_90d["Ticker"]), f"{strongest_90d['Company']} · {_fmt_pct(strongest_90d.get('90D %'))}"),
                ("Weakest 5D", str(weakest_5d["Ticker"]), f"{weakest_5d['Company']} · {_fmt_pct(weakest_5d.get('5D %'))}"),
            ]
            cols = st.columns(4)
            for col, (label, value, caption) in zip(cols, summary_cards):
                with col:
                    st.markdown(
                        f'<div class="card"><div class="metric-label">{label}</div><div class="metric-value" style="font-size:1.15rem;">{value}</div><div class="muted" style="font-size:.82rem;">{caption}</div></div>',
                        unsafe_allow_html=True,
                    )
            st.plotly_chart(peer_timeframe_comparison_chart(peer_df), use_container_width=True)
            display_cols = ["Ticker", "Company", "Targets", "Channels", "5D %", "30D %", "60D %", "90D %", "Read"]
            display_cols = [c for c in display_cols if c in peer_df.columns]
            with st.expander("Click to see granular peer table"):
                st.dataframe(peer_df[display_cols], use_container_width=True, hide_index=True)

        bundle = getattr(results, "data_bundle", None)
        if bundle is not None and bundle.failures:
            with st.expander("Data gaps safely handled"):
                st.write(bundle.failures)


    if active_page == "Channel Intelligence":
        st.markdown('<div class="section-title">Channel Intelligence</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                Backend-classified channels for direct read-through, ADC capital flow, ovarian cancer, and separate Alzheimer’s / bone disease side lanes.
                The chart uses 30D average performance as the bar and 5D average performance as the marker, while the table preserves the Quarterly 90D view for quarter-like context.
            </div>
            """,
            unsafe_allow_html=True,
        )
        channel_table = getattr(results, "channel_table", None)
        if channel_table is None or channel_table.empty:
            st.info("Channel intelligence is unavailable because peer market data did not return usable history.")
        else:
            st.plotly_chart(channel_momentum_chart(channel_table), use_container_width=True)
            st.dataframe(channel_table, use_container_width=True, hide_index=True)


    if active_page == "Catalyst & Capital":
        st.markdown('<div class="section-title">Catalyst & Capital Intelligence</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                v0.6 translates catalyst rows into meaning: phase, current positioning, read-through, and what leadership should watch.
                Manual catalyst curation is still only a bridge; the backend ingestion hook remains ready for future scraping/API feeds.
            </div>
            """,
            unsafe_allow_html=True,
        )

        cards = getattr(results, "catalyst_cards", None) or []
        if cards:
            ccols = st.columns(len(cards))
            for col, card in zip(ccols, cards):
                with col:
                    st.markdown(
                        f"""
                        <div class="card">
                            <div class="metric-label">{card['label']}</div>
                            <div class="metric-value" style="font-size:1.2rem;">{card['value']}</div>
                            <div class="muted" style="font-size:.82rem;">{card['caption']}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        catalyst_insights = getattr(results, "catalyst_insights", None) or []
        capital_insights = getattr(results, "capital_flow_insights", None) or []
        event_insights = getattr(results, "event_reaction_insights", None) or []
        cols = st.columns(3)
        with cols[0]:
            st.markdown('<div class="section-title" style="font-size:1rem;">Catalyst Meaning</div>', unsafe_allow_html=True)
            for line in catalyst_insights[:4]:
                st.markdown(f'<div class="insight">{line}</div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown('<div class="section-title" style="font-size:1rem;">Capital Flow</div>', unsafe_allow_html=True)
            for line in capital_insights[:4]:
                st.markdown(f'<div class="insight">{line}</div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown('<div class="section-title" style="font-size:1rem;">Event Reaction</div>', unsafe_allow_html=True)
            for line in event_insights[:4]:
                st.markdown(f'<div class="insight">{line}</div>', unsafe_allow_html=True)

        catalyst_table = getattr(results, "catalyst_table", None)
        capital_table = getattr(results, "capital_flow_table", None)
        event_table = getattr(results, "event_reaction_table", None)
        left_col, right_col = st.columns(2, gap="large")
        with left_col:
            if catalyst_table is not None and not catalyst_table.empty:
                st.plotly_chart(catalyst_priority_chart(catalyst_table), use_container_width=True)
                display_cols = ["ticker", "company", "asset", "target", "phase", "market_positioning", "expected_timing", "impact", "read_through", "what_it_means"]
                st.dataframe(catalyst_table[display_cols], use_container_width=True, hide_index=True)
            else:
                st.info("No catalyst records are currently available.")
        with right_col:
            if capital_table is not None and not capital_table.empty:
                st.plotly_chart(capital_flow_chart(capital_table), use_container_width=True)
                st.dataframe(capital_table, use_container_width=True, hide_index=True)
            else:
                st.info("Capital-flow analysis is unavailable because channel data is incomplete.")

        if event_table is not None and not event_table.empty:
            with st.expander("Event reaction table"):
                st.dataframe(event_table, use_container_width=True, hide_index=True)

        backlog = getattr(results, "ingestion_backlog", None)
        if backlog is not None and not backlog.empty:
            with st.expander("Future backend ingestion hook"):
                st.markdown(
                    """
                    This is intentionally hidden behind the scenes for now. It documents where automated scraping/API ingestion will plug in later,
                    while the CEO-facing surface remains simple.
                    """
                )
                st.dataframe(backlog, use_container_width=True, hide_index=True)


    if active_page == "Technical + Catalyst":
        st.markdown('<div class="section-title">Technical + Catalyst Positioning</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                v0.8.7 verifies that real technical analysis, catalyst timing, and adaptive market activation. The goal is not to say buy or sell;
                it is to explain whether the stock is technically setting up ahead of its catalyst compared with peers.
            </div>
            """,
            unsafe_allow_html=True,
        )
        snap = getattr(results, "technical_snapshot", None)
        timing = getattr(results, "catalyst_timing", None)
        align = getattr(results, "alignment_summary", None)
        tech_table = getattr(results, "technical_table", None)
        peer_read = getattr(results, "peer_technical_read", None) or []

        if snap and align:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="card"><div class="metric-label">NXTC Setup</div><div class="metric-value">{snap.setup_score:.1f}/10</div><div class="muted">{snap.setup_state}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="card"><div class="metric-label">Trend State</div><div class="metric-value" style="font-size:1rem;">{snap.trend_state}</div><div class="muted">EMA20/50/200 + structure</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="card"><div class="metric-label">Catalyst</div><div class="metric-value" style="font-size:1rem;">{timing.nxtc_timing if timing else "Unavailable"}</div><div class="muted">{timing.nxtc_asset if timing else "Primary event"}</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="card"><div class="metric-label">Alignment</div><div class="metric-value" style="font-size:1rem;">{align.label}</div><div class="muted">Technical + catalyst read</div></div>', unsafe_allow_html=True)

            left, right = st.columns(2, gap="large")
            with left:
                st.markdown('<div class="section-title" style="font-size:1rem;">NXTC Technical Interpretation</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>Interpretation:</b> {snap.interpretation}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>Momentum:</b> {snap.momentum_state}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>Accumulation:</b> {snap.accumulation_state}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>Exhaustion:</b> {snap.exhaustion_state}</div>', unsafe_allow_html=True)
                if snap.confirmation_signals:
                    st.markdown('<div class="section-title" style="font-size:.95rem;">Confirmation Signals</div>', unsafe_allow_html=True)
                    for item in snap.confirmation_signals[:4]:
                        st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)
                if snap.risk_signals:
                    st.markdown('<div class="section-title" style="font-size:.95rem;">Risk Signals</div>', unsafe_allow_html=True)
                    for item in snap.risk_signals[:4]:
                        st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="section-title" style="font-size:1rem;">Catalyst Timing vs Peers</div>', unsafe_allow_html=True)
                if timing:
                    st.markdown(f'<div class="insight"><b>NXTC primary event:</b> {timing.nxtc_primary_event}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="insight"><b>Timing:</b> {timing.nxtc_timing}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="insight"><b>Peer timing read:</b> {timing.peer_timing_read}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="insight"><b>Meaning:</b> {timing.timing_interpretation}</div>', unsafe_allow_html=True)
                st.markdown('<div class="section-title" style="font-size:1rem;">Alignment Signal</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>{align.label}</b>: {align.explanation}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>What this means:</b> {align.what_it_means}</div>', unsafe_allow_html=True)
                for item in align.watch[:4]:
                    st.markdown(f'<div class="insight">Watch: {item}</div>', unsafe_allow_html=True)

            if tech_table is not None and not tech_table.empty:
                st.plotly_chart(technical_setup_chart(tech_table), use_container_width=True)
                for line in peer_read:
                    st.markdown(f'<div class="insight">{line}</div>', unsafe_allow_html=True)
                with st.expander("Technical score table"):
                    st.dataframe(tech_table, use_container_width=True, hide_index=True)
            if timing and timing.timeline_table is not None and not timing.timeline_table.empty:
                with st.expander("Catalyst timing map"):
                    st.dataframe(timing.timeline_table, use_container_width=True, hide_index=True)
        else:
            st.info("Technical + catalyst positioning is unavailable because required NXTC data or catalyst timing is incomplete.")


    if active_page == "Strategy & Timing":
        st.markdown('<div class="section-title">Strategy & Timing Intelligence</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="muted" style="margin-bottom: .85rem;">
                Corporate strategy timing layer: market regime, window score, suggested actions, and scenario watch cases.
                This is not trading advice; it is CEO communication and investor-outreach context.
            </div>
            """,
            unsafe_allow_html=True,
        )
        regime = getattr(results, "market_regime", None)
        score = getattr(results, "window_score", None)
        strat = getattr(results, "strategy_summary", None)
        activation = getattr(results, "activation_summary", None)
        scenarios = getattr(results, "scenario_outlook", None) or []

        if activation:
            st.markdown('<div class="section-title" style="font-size:1rem;">Market Activation</div>', unsafe_allow_html=True)
            a1, a2, a3 = st.columns(3, gap="medium")
            with a1:
                st.markdown(f'<div class="card"><div class="metric-label">Market Attention</div><div class="metric-value" style="font-size:1.2rem;">{activation.market_attention}</div><div class="muted">{activation.activation_state}</div></div>', unsafe_allow_html=True)
            with a2:
                st.markdown(f'<div class="card"><div class="metric-label">Activation Score</div><div class="metric-value" style="font-size:1.2rem;">{activation.activation_score:.1f}/10</div><div class="muted">Adaptive from market, technical, catalyst, and ADC inputs</div></div>', unsafe_allow_html=True)
            with a3:
                st.markdown(f'<div class="card"><div class="metric-label">Operator Watch</div><div class="metric-value" style="font-size:1.0rem;">Adaptive</div><div class="muted">Recommendations change with incoming data</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="executive-narrative"><div class="summary-title">What this means operationally</div><div class="summary-body">{activation.summary}<br><br>{activation.why_it_matters}</div></div>', unsafe_allow_html=True)
            with st.expander("Why this activation read was generated"):
                st.dataframe(pd.DataFrame([{"Component": k, "Score": v} for k, v in activation.components.items()]), use_container_width=True, hide_index=True)
                paths = getattr(activation, "triggered_paths", []) or []
                evidence = getattr(activation, "evidence", []) or []
                if paths:
                    st.markdown("**Logic paths triggered**")
                    st.dataframe(pd.DataFrame([{"Triggered path": p} for p in paths]), use_container_width=True, hide_index=True)
                if evidence:
                    st.markdown("**Input evidence used**")
                    st.dataframe(pd.DataFrame([{"Evidence": e} for e in evidence]), use_container_width=True, hide_index=True)
            st.markdown('<div class="section-title" style="font-size:1rem;">Adaptive Actions</div>', unsafe_allow_html=True)
            for action in activation.recommended_actions:
                st.markdown(f'<div class="insight">{action}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="insight"><b>Watch signal:</b> {activation.watch_signal}</div>', unsafe_allow_html=True)

        if regime and score:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="card"><div class="metric-label">Window Score</div><div class="metric-value">{score.score:.1f}/10</div><div class="muted">{score.label}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="card"><div class="metric-label">Biotech Regime</div><div class="metric-value" style="font-size:1.2rem;">{regime.biotech_regime}</div><div class="muted">XBI 30D/90D posture</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="card"><div class="metric-label">ADC Regime</div><div class="metric-value" style="font-size:1.2rem;">{regime.adc_regime}</div><div class="muted">ADC capital-flow lane</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="card"><div class="metric-label">NXTC Regime</div><div class="metric-value" style="font-size:1.05rem;">{regime.nxtc_regime}</div><div class="muted">Relative to sector</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="insight"><b>Window Interpretation:</b> {score.interpretation}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="insight"><b>Regime Read:</b> {regime.combined_read}</div>', unsafe_allow_html=True)
            cap_summary = getattr(results, "capital_flow_summary", None)
            if cap_summary is not None:
                st.markdown(
                    f'<div class="insight"><b>ADC Regime Explanation:</b> {regime.adc_regime}. '
                    f'The ADC lane read is based on {cap_summary.adc_posture.lower()} and the channel-level return stack, '
                    f'not a manual toggle. {cap_summary.divergence_note}</div>',
                    unsafe_allow_html=True,
                )

            comp_df = pd.DataFrame([{"Component": k, "Score": v} for k, v in score.components.items()])
            st.dataframe(comp_df, use_container_width=True, hide_index=True)

        if strat:
            left, right = st.columns(2, gap="large")
            with left:
                st.markdown('<div class="section-title" style="font-size:1rem;">Suggested Actions</div>', unsafe_allow_html=True)
                for action in strat.suggested_actions:
                    st.markdown(f'<div class="insight">{action}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="insight"><b>Press Timing:</b> {strat.press_timing}</div>', unsafe_allow_html=True)
            with right:
                st.markdown('<div class="section-title" style="font-size:1rem;">Watch Items</div>', unsafe_allow_html=True)
                for item in strat.watch_items:
                    st.markdown(f'<div class="insight">{item}</div>', unsafe_allow_html=True)

        if scenarios:
            st.markdown('<div class="section-title" style="font-size:1rem;">Scenario Outlook</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(scenarios), use_container_width=True, hide_index=True)


    if active_page == "Market Rhythm":
        st.markdown('<div class="section-title">Early Time-Cycle Overlay</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="card">
                <div class="muted">
                    Prototype placeholder: this section will show recurring biotech momentum windows, catalyst-adjacent
                    performance rhythm, and capital-market timing context. In Iteration 3/4, this will be fed by real
                    price history and event windows rather than mock commentary.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.write("")


render_buildwell_emblem()
