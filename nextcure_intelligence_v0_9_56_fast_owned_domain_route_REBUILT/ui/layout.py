"""Reusable layout fragments for the dashboard."""

from __future__ import annotations

from html import escape
from pathlib import Path
import base64

import streamlit as st

from config.settings import APP_SUBTITLE, APP_TITLE, APP_VERSION


def render_hero() -> None:
    st.markdown(
        f"""
        <div class="hero hero-compact hero-centered">
            <div class="hero-topline centered">
                <div class="status-pill">● {APP_VERSION}</div>
            </div>
            <h1>{APP_TITLE}</h1>
            <div class="hero-subtitle">{APP_SUBTITLE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _card_html(label: str, value: str, caption: str = "", detail: str | None = None, card_class: str = "card") -> str:
    detail_html = f'<div class="detail-pill">Detail: {escape(detail)}</div>' if detail else ""
    return (
        f'<div class="{card_class}">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f'<div class="muted card-caption">{escape(caption)}</div>'
        f'{detail_html}'
        f'</div>'
    )


def render_kpi_cards(kpis: list[dict[str, str]]) -> None:
    cols = st.columns(len(kpis))
    for col, item in zip(cols, kpis):
        with col:
            st.markdown(
                _card_html(str(item["label"]), str(item["value"]), str(item.get("caption", ""))),
                unsafe_allow_html=True,
            )


def render_dashboard_nav(pages: list[str], active_page: str) -> str:
    """Render a clean jump menu for dashboard sections.

    The Executive Summary remains the default landing page after each run, while
    this menu keeps deeper analysis sections accessible without a noisy row of
    navigation buttons.
    """
    if active_page not in pages:
        active_page = "Executive Summary"

    # Only initialize the selectbox value when missing/invalid.
    # Do not reset it to active_page on every rerun, otherwise selecting
    # another section gets overwritten before navigation can occur.
    if st.session_state.get("dashboard_jump_to") not in pages:
        st.session_state.dashboard_jump_to = active_page

    st.markdown(
        """
        <div class="jump-nav-wrap">
            <div class="jump-line"></div>
            <div class="jump-center-title">Jump to a deeper intelligence layer</div>
            <div class="jump-line"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_left, nav_mid, nav_right = st.columns([0.31, 0.38, 0.31])
    with nav_mid:
        st.markdown('<div class="jump-select-shell">', unsafe_allow_html=True)
        selected = st.selectbox(
            "Jump to dashboard section",
            options=pages,
            index=pages.index(st.session_state.dashboard_jump_to),
            key="dashboard_jump_to",
            label_visibility="collapsed",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    st.session_state.active_page = selected
    return selected

def render_buildwell_emblem() -> None:
    """Render a subtle Built By BuildWell linked emblem."""
    emblem_path = Path(__file__).resolve().parents[1] / "assets" / "buildwell_emblem.png"
    if not emblem_path.exists():
        return
    encoded = base64.b64encode(emblem_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <div class="buildwell-footer">
            <a href="https://www.BuiltByBuildWell.com" target="_blank" rel="noopener noreferrer" aria-label="Built By BuildWell">
                <img src="data:image/png;base64,{encoded}" alt="Built By BuildWell" />
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _summary_title(line: str) -> str:
    if ":" in line:
        return line.split(":", 1)[0]
    return "Readout"


def _summary_body(line: str) -> str:
    if ":" in line:
        return line.split(":", 1)[1].strip()
    return line


def _is_detail_line(line: str) -> bool:
    lower = line.lower()
    detail_markers = [
        "cdh6 / ovarian adc:",
        "b7-h4 adc:",
        "adc capital flow:",
        "ovarian cancer:",
        "data quality note:",
        "capital is strongest",
        "capital is weakest",
        "nxtc event positioning",
    ]
    return any(marker in lower for marker in detail_markers)


def _build_executive_narrative(insights: list[str]) -> str:
    joined = " ".join(insights).lower()
    activation = next((line for line in insights if line.lower().startswith("market activation")), "")
    action = next((line for line in insights if line.lower().startswith("what you can do")), "")

    if "not currently being rewarded" in joined or "stock-specific weakness" in joined:
        p1 = "The current read is defensive: NXTC is not being rewarded versus XBI and the broader biotech tape is not providing much help."
    elif "outperform" in joined or "constructive" in joined:
        p1 = "The current read is constructive: NXTC is showing signs of better positioning, but the quality of that move still needs to be checked against volume, peers, and catalyst timing."
    else:
        p1 = "The current read is selective: some signals are useful, but the market has not fully aligned behind the story yet."

    if activation:
        activation_body = _summary_body(activation)
        p2 = activation_body
    else:
        p2 = "The practical question is not only whether the technicals improve, but whether investors understand the upcoming catalyst well enough to start positioning ahead of it."

    if action:
        p3 = _summary_body(action)
        return f"{p1} {p2} Operator lens: {p3}"
    return p1 + " " + p2


def render_insights(insights: list[str]) -> None:
    st.markdown('<div class="section-title">Executive Readout</div>', unsafe_allow_html=True)
    if not insights:
        st.markdown('<div class="insight">No executive readout is available yet.</div>', unsafe_allow_html=True)
        return

    top_lines = [line for line in insights if not _is_detail_line(line)][:5]
    detail_lines = [line for line in insights if line not in top_lines]

    st.markdown(
        f'<div class="executive-narrative"><div class="summary-title">Plain-English CEO summary</div>'
        f'<div class="summary-body">{escape(_build_executive_narrative(insights))}</div></div>',
        unsafe_allow_html=True,
    )

    for row_start in range(0, len(top_lines), 2):
        row = top_lines[row_start:row_start + 2]
        cols = st.columns(len(row), gap="medium")
        for col, line in zip(cols, row):
            with col:
                st.markdown(
                    f'<div class="summary-card"><div class="summary-title">{escape(_summary_title(line))}</div>'
                    f'<div class="summary-body">{escape(_summary_body(line))}</div></div>',
                    unsafe_allow_html=True,
                )

    if detail_lines:
        with st.expander("Click to see more granular channel, catalyst, and technical detail"):
            for insight in detail_lines:
                st.markdown(f'<div class="insight">{escape(insight)}</div>', unsafe_allow_html=True)


def _detail_target(label: str) -> str:
    text = label.lower()
    if "technical" in text or "alignment" in text:
        return "Technical + Catalyst"
    if "catalyst" in text or "capital" in text:
        return "Catalyst & Capital"
    if "adc" in text or "ovarian" in text or "quarter" in text:
        return "Channel Intelligence"
    if "synthesis" in text or "interpretation" in text or "strategic relevance" in text:
        return "Interpretation Engine"
    if "attention" in text or "activation" in text:
        return "Strategy & Timing"
    if "market" in text or "nxtc" in text or "driver" in text or "window" in text:
        return "Strategy & Timing"
    return "Relevant tab"


def _priority_watch_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    keep = {"Market", "NXTC Posture", "Driver", "Window Score", "Market Attention", "Catalyst Phase", "Technical Setup", "Alignment", "Synthesis"}
    prioritized = [item for item in items if str(item.get("label", "")) in keep]
    # keep order stable, but avoid showing too many cards at the top
    return prioritized[:8]


def render_watch_items(items: list[dict[str, str]]) -> None:
    if not items:
        return
    st.markdown('<div class="section-title">Intelligence Snapshot</div>', unsafe_allow_html=True)
    visible_items = _priority_watch_items(items)
    if not visible_items:
        visible_items = items[:6]

    for row_start in range(0, len(visible_items), 4):
        row = visible_items[row_start:row_start + 4]
        cols = st.columns(len(row), gap="medium")
        for col, item in zip(cols, row):
            label = str(item.get("label", ""))
            value = str(item.get("value", ""))
            caption = str(item.get("caption", ""))
            target = _detail_target(label)
            with col:
                st.markdown(
                    _card_html(label, value, caption, card_class="snapshot-card"),
                    unsafe_allow_html=True,
                )
                if st.button(f"View {target} →", key=f"detail_{label}_{row_start}"):
                    st.session_state.active_page = target
                    st.rerun()



def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        if hasattr(value, "__float__"):
            import math
            number = float(value)
            return None if math.isnan(number) else number
    except Exception:
        return None
    return None


def _pct(value: object) -> str:
    number = _safe_float(value)
    return "N/A" if number is None else f"{number:+.1f}%"


def _return_value(return_table, ticker: str, column: str) -> float | None:
    if return_table is None or getattr(return_table, "empty", True):
        return None
    try:
        row = return_table[return_table["Ticker"].astype(str) == ticker]
        if row.empty or column not in row.columns:
            return None
        return _safe_float(row.iloc[0][column])
    except Exception:
        return None


def _first_nonempty(items: list[str], fallback: str) -> str:
    for item in items:
        text = str(item).strip()
        if text:
            return text
    return fallback


def _plain_list(items: list[str], limit: int = 3) -> str:
    clean = [str(x).strip() for x in items if str(x).strip()]
    if not clean:
        return '<div class="exec-empty">No elevated item for this run.</div>'
    return "".join(f'<div class="exec-bullet">{escape(item)}</div>' for item in clean[:limit])


def _status_tone(value: float | None, higher_is_good: bool = True) -> str:
    if value is None:
        return "neutral"
    if higher_is_good:
        return "positive" if value >= 0 else "negative"
    return "negative" if value >= 0 else "positive"




def _quarterly_state(value: float | None) -> str:
    if value is None:
        return "Neutral"
    if value >= 5:
        return "Quarterly strength"
    if value <= -5:
        return "Quarterly pressure"
    return "Quarterly neutral"


def _channel_by_label(channel_summaries) -> dict[str, object]:
    return {str(getattr(ch, "label", "")): ch for ch in (channel_summaries or [])}


def _quarterly_lane_reads(channel_summaries) -> list[str]:
    """Always elevate the key quarterly lane states into the trend section."""
    by_label = _channel_by_label(channel_summaries)
    wanted = [
        ("ADC holistic", "ADC Capital Flow"),
        ("CDH6 / Ovarian ADC", "CDH6 / Ovarian ADC"),
        ("B7-H4", "B7-H4 ADC"),
        ("Alzheimer's side channel", "Alzheimer's Side Channel"),
        ("Bone disease side channel", "Bone Disease Side Channel"),
    ]
    reads: list[str] = []
    for display, label in wanted:
        ch = by_label.get(label)
        if ch is None:
            reads.append(f"{display}: Quarterly neutral until enough comparable market data is available.")
            continue
        avg_90d = _safe_float(getattr(ch, "avg_90d", None))
        state = _quarterly_state(avg_90d)
        detail = "N/A" if avg_90d is None else f"{avg_90d:+.1f}% 90D basket average"
        reads.append(f"{display}: {state} ({detail}).")
    return reads



def _clinical_bucket_lines(clinical, bucket: str, limit: int = 2) -> list[str]:
    if clinical is None:
        return []
    signals = list(getattr(clinical, "signals", []) or [])
    lines: list[str] = []
    for signal in signals:
        if getattr(signal, "bucket", "") != bucket:
            continue
        # Executive summary should show the adaptive insight fragment only.
        # Supporting value/evidence remains available in the Fresh Intelligence drill-down.
        text = str(getattr(signal, "finding", "") or getattr(signal, "value", "")).strip()
        if text:
            lines.append(text)
    return lines[:limit]


def _clinical_status_line(clinical) -> str | None:
    if clinical is None:
        return None
    status = str(getattr(clinical, "source_status", "unknown")).title()
    total = int(getattr(clinical, "total_trials", 0) or 0)
    active = int(getattr(clinical, "active_trials", 0) or 0)
    lanes = len(getattr(clinical, "lanes_covered", []) or [])
    if total <= 0:
        return f"ClinicalTrials.gov source status: {status}. No clinical-landscape conclusion was elevated in this run."
    return f"ClinicalTrials.gov source status: live. External clinical-development signals were incorporated into the four executive buckets."

def render_premium_executive_summary(results) -> None:
    """Render the premium, compressed CEO-facing dashboard surface."""
    synthesis = getattr(results, "synthesis_summary", None)
    return_table = getattr(results, "return_table", None)
    classification = getattr(results, "classification", None)
    channel_summaries = list(getattr(results, "channel_summaries", []) or [])
    clinical = getattr(results, "clinical_trials", None)

    nxtc_5d = _return_value(return_table, "NXTC", "5D %")
    nxtc_30d = _return_value(return_table, "NXTC", "30D %")
    qqq_5d = _return_value(return_table, "QQQ", "5D %")
    spread_xbi = getattr(classification, "spread_5d_xbi", None)
    spread_qqq = None if nxtc_5d is None or qqq_5d is None else nxtc_5d - qqq_5d

    headline = _first_nonempty([
        getattr(synthesis, "headline", "") if synthesis is not None else "",
        "Executive intelligence run complete.",
    ], "Executive intelligence run complete.")

    fresh_lines = []
    fresh_lines.extend(_clinical_bucket_lines(clinical, "new_information", limit=3))
    if synthesis is not None:
        fresh_lines.extend(list(getattr(synthesis, "what_changed", []) or [])[:1])

    value_lines = []
    value_lines.extend(_clinical_bucket_lines(clinical, "value", limit=3))
    if synthesis is not None:
        value_lines.extend(list(getattr(synthesis, "competitive_edges", []) or [])[:1])

    trend_lines = _quarterly_lane_reads(channel_summaries)
    trend_lines.extend(_clinical_bucket_lines(clinical, "trend", limit=3))
    if synthesis is not None:
        trend_lines.extend(list(getattr(synthesis, "trend_radar", []) or [])[:2])
    if not trend_lines and synthesis is not None:
        trend_lines.extend(list(getattr(synthesis, "operating_recommendations", []) or [])[:2])

    position_lines = []
    if spread_xbi is not None:
        position_lines.append(f"NXTC is {_pct(spread_xbi)} versus XBI over 5D, separating company-specific behavior from the biotech tape.")
    if spread_qqq is not None:
        position_lines.append(f"NXTC is {_pct(spread_qqq)} versus QQQ over 5D, showing whether growth-market risk appetite is helping or masking the move.")
    if nxtc_30d is not None:
        position_lines.append(f"NXTC 30D posture is {_pct(nxtc_30d)}, which anchors whether the move is a short-term bounce or a medium-term repair.")
    position_lines.extend(_clinical_bucket_lines(clinical, "positioning", limit=1))
    if synthesis is not None:
        gaps = getattr(synthesis, "competitive_gap_table", None)
        if gaps is not None and not gaps.empty:
            top = gaps.iloc[0]
            ticker = str(top.get('Ticker', 'Peer'))
            channels = str(top.get('Channels', 'the monitored peer basket'))
            position_lines.append(f"Peer context: {ticker} is currently receiving stronger market attention inside {channels}. The useful question is what investors are rewarding there that NXTC is not yet getting credit for.")

    st.markdown(
        f"""
        <div class="exec-brief-shell">
            <div class="exec-kicker">Executive Intelligence Brief</div>
            <div class="exec-hero-line">{escape(headline)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4, gap="medium")
    stats = [
        ("NXTC 5D", _pct(nxtc_5d), "Company tape", _status_tone(nxtc_5d)),
        ("vs XBI", _pct(spread_xbi), "Biotech relative", _status_tone(_safe_float(spread_xbi))),
        ("vs QQQ", _pct(spread_qqq), "Growth-market relative", _status_tone(spread_qqq)),
        ("NXTC 30D", _pct(nxtc_30d), "Medium-term posture", _status_tone(nxtc_30d)),
    ]
    for col, (label, value, caption, tone) in zip(cols, stats):
        with col:
            st.markdown(
                f'<div class="exec-stat {tone}"><div class="exec-stat-label">{escape(label)}</div><div class="exec-stat-value">{escape(value)}</div><div class="exec-stat-caption">{escape(caption)}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="exec-section-label">The Four Questions This Run Answers</div>', unsafe_allow_html=True)
    cards = [
        ("01", "What new information did we find?", fresh_lines, "New clinical and market movement worth knowing."),
        ("02", "Why is that information valuable?", value_lines, "Board-ready implications from the clinical structure."),
        ("03", "What trends can be inferred?", trend_lines, "Lane-by-lane direction without blending the stories."),
        ("04", "How is NXTC positioned?", position_lines, "Market behavior connected to the CDH6 positioning thesis."),
    ]
    accordion_parts = ['<div class="exec-accordion-shell">']
    for num, title, lines, caption in cards:
        open_attr = " open" if num == "01" else ""
        hint = "Open first · tap to close" if num == "01" else "Tap to expand"
        item_limit = 8 if num == "03" else 5
        accordion_parts.append(
            '<details class="exec-answer-details"' + open_attr + '>'
            '<summary>'
            f'<span class="exec-summary-number">{escape(num)}</span>'
            f'<span class="exec-summary-title">{escape(title)}</span>'
            f'<span class="exec-summary-hint">{escape(hint)}</span>'
            '</summary>'
            '<div class="exec-answer-strip">'
            '<div class="exec-strip-content">'
            f'<div class="exec-strip-title">{escape(title)}</div>'
            f'<div class="exec-card-caption">{escape(caption)}</div>'
            f'<div class="exec-card-body">{_plain_list(lines, limit=item_limit)}</div>'
            '</div>'
            '</div>'
            '</details>'
        )
    accordion_parts.append('</div>')
    st.markdown("".join(accordion_parts), unsafe_allow_html=True)

    if synthesis is not None:
        recs = list(getattr(synthesis, "operating_recommendations", []) or [])[:3]
        edges = list(getattr(synthesis, "competitive_edges", []) or [])[:3]
        bottom_left, bottom_right = st.columns([0.52, 0.48], gap="large")
        with bottom_left:
            st.markdown(
                f"""
                <div class="exec-focus-panel">
                    <div class="exec-panel-title">Leadership Focus</div>
                    <div class="exec-panel-copy">{_plain_list(recs, limit=3)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with bottom_right:
            st.markdown(
                f"""
                <div class="exec-focus-panel secondary">
                    <div class="exec-panel-title">Competitive Edge Watch</div>
                    <div class="exec-panel-copy">{_plain_list(edges, limit=3)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with st.expander("Supporting evidence from this run"):
        st.caption("The Executive Summary is intentionally compressed. Granular analysis remains available in the other tabs.")
        rt = getattr(results, "return_table", None)
        if rt is not None and not rt.empty:
            st.dataframe(rt, use_container_width=True, hide_index=True)
        sponsor_table = getattr(clinical, "sponsor_discovery_table", None) if clinical is not None else None
        if sponsor_table is not None and not sponsor_table.empty:
            st.markdown("**Dynamically discovered sponsor registry**")
            st.dataframe(sponsor_table, use_container_width=True, hide_index=True)
        audit_table = getattr(clinical, "discovery_audit_table", None) if clinical is not None else None
        if audit_table is not None and not audit_table.empty:
            st.markdown("**ClinicalTrials.gov discovery audit**")
            st.dataframe(audit_table, use_container_width=True, hide_index=True)
        clinical_table = getattr(clinical, "trial_table", None) if clinical is not None else None
        if clinical_table is not None and not clinical_table.empty:
            st.markdown("**ClinicalTrials.gov live records**")
            st.dataframe(clinical_table, use_container_width=True, hide_index=True)
        gaps = getattr(synthesis, "competitive_gap_table", None) if synthesis is not None else None
        if gaps is not None and not gaps.empty:
            st.markdown("**Competitive read-through table**")
            st.dataframe(gaps, use_container_width=True, hide_index=True)

def render_synthesis_summary(synthesis) -> None:
    """Render v0.9 interpretation/synthesis layer."""
    if synthesis is None:
        return

    st.markdown('<div class="section-title">Interpretation Engine</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="executive-narrative"><div class="summary-title">Synthesized meaning</div>'
        f'<div class="summary-body">{escape(str(synthesis.headline))}<br><br>{escape(str(synthesis.thesis))}</div></div>',
        unsafe_allow_html=True,
    )

    cards = list(getattr(synthesis, "signal_cards", []) or [])
    for row_start in range(0, len(cards), 2):
        row = cards[row_start:row_start + 2]
        cols = st.columns(len(row), gap="medium")
        for col, card in zip(cols, row):
            with col:
                st.markdown(
                    f'<div class="synthesis-card">'
                    f'<div class="metric-label">{escape(str(card.label))}</div>'
                    f'<div class="metric-value" style="font-size:1.12rem;">{escape(str(card.state))}</div>'
                    f'<div class="summary-body" style="margin-top:.55rem;">{escape(str(card.meaning))}</div>'
                    f'<div class="detail-pill">Evidence: {escape(str(card.evidence))}</div>'
                    f'<div class="muted" style="margin-top:.7rem; font-size:.82rem;">Implication: {escape(str(card.implication))}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


    relevance = getattr(synthesis, "strategic_relevance", None)
    if relevance is not None:
        st.markdown('<div class="section-title" style="font-size:1rem;">Strategic Relevance Engine</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="executive-narrative"><div class="summary-title">Personalized to NextCure</div>'
            f'<div class="summary-body">{escape(str(relevance.headline))}</div></div>',
            unsafe_allow_html=True,
        )
        brief = getattr(relevance, "executive_brief", []) or []
        if brief:
            cols = st.columns(2, gap="medium")
            for idx, item in enumerate(brief[:4]):
                with cols[idx % 2]:
                    st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)

        signal_table = getattr(relevance, "signal_table", None)
        if signal_table is not None and not signal_table.empty:
            st.markdown('<div class="section-title" style="font-size:.95rem;">Relevance-Scored Incoming Signal Map</div>', unsafe_allow_html=True)
            st.dataframe(signal_table, use_container_width=True, hide_index=True)

        theme_table = getattr(relevance, "theme_table", None)
        if theme_table is not None and not theme_table.empty:
            st.markdown('<div class="section-title" style="font-size:.95rem;">Repeated Theme Concentration</div>', unsafe_allow_html=True)
            st.dataframe(theme_table, use_container_width=True, hide_index=True)


    st.markdown('<div class="section-title" style="font-size:1rem;">New Intelligence: Delta / Gap Detection</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="muted" style="margin-bottom:.65rem;">This is the differentiated layer: it looks for lane acceleration, fading, NXTC perception gaps, and peer read-through signals instead of repeating the executive narrative.</div>',
        unsafe_allow_html=True,
    )

    delta_table = getattr(synthesis, "insight_delta_table", None)
    if delta_table is not None and not delta_table.empty:
        st.dataframe(delta_table, use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="insight">No lane-level delta signal was strong enough to elevate in this run.</div>', unsafe_allow_html=True)

    gap_table = getattr(synthesis, "competitive_gap_table", None)
    if gap_table is not None and not gap_table.empty:
        st.markdown('<div class="section-title" style="font-size:1rem;">Competitive Read-Through Signals</div>', unsafe_allow_html=True)
        st.dataframe(gap_table, use_container_width=True, hide_index=True)

    radar_items = getattr(synthesis, "trend_radar", []) or []
    if radar_items:
        st.markdown('<div class="section-title" style="font-size:1rem;">Trend Radar</div>', unsafe_allow_html=True)
        for item in radar_items:
            st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="section-title" style="font-size:1rem;">What Changed / What Matters</div>', unsafe_allow_html=True)
        for item in getattr(synthesis, "what_changed", []) or []:
            st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-title" style="font-size:1rem;">Emerging Competitive Edges</div>', unsafe_allow_html=True)
        for item in getattr(synthesis, "competitive_edges", []) or []:
            st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title" style="font-size:1rem;">Operating Recommendations</div>', unsafe_allow_html=True)
    for item in getattr(synthesis, "operating_recommendations", []) or []:
        st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)

    questions = getattr(synthesis, "next_questions", []) or []
    if questions:
        st.markdown('<div class="section-title" style="font-size:1rem;">Questions This Layer Now Answers</div>', unsafe_allow_html=True)
        for item in questions:
            st.markdown(f'<div class="insight">{escape(str(item))}</div>', unsafe_allow_html=True)

