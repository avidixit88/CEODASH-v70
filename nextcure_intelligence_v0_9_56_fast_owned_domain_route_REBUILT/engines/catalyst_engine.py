"""Catalyst intelligence engine.

v0.6 upgrades catalysts from a static list into CEO-readable context: phase,
positioning, meaning, support signals, and watch risks. Manual curation remains
a bridge only; the schema is designed for future scraper/API ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config.catalysts import CATALYST_EVENTS, future_ingestion_backlog
from engines.relative_performance_engine import safe_return


IMPACT_SCORE = {"High": 3, "Medium": 2, "Low": 1}
READ_SCORE = {"Primary": 4, "High": 3, "Medium-High": 2.5, "Medium": 2, "Separate channel": 1, "Low": 1}


@dataclass(frozen=True)
class CatalystSummary:
    total_events: int
    high_impact_events: int
    primary_events: int
    highest_priority: str
    ingestion_note: str
    primary_phase: str = "Unavailable"
    primary_positioning: str = "Unavailable"
    primary_meaning: str = "No primary catalyst context available."


def _infer_phase(event: pd.Series) -> str:
    timing = str(event.get("expected_timing", "")).lower()
    status = str(event.get("status", "")).lower()
    category = str(event.get("category", "")).lower()
    if "asco" in timing or "q2 2026" in timing or status == "upcoming":
        return "Pre-catalyst"
    if "ongoing" in timing or status == "active":
        return "Active read-through"
    if "partner" in category or status == "watch":
        return "Partnering watch"
    return "Monitoring"


def _positioning_label(ticker: str, return_table: pd.DataFrame | None) -> str:
    if return_table is None or return_table.empty:
        return "Market data pending"
    r5 = safe_return(return_table, ticker, "5D %")
    r30 = safe_return(return_table, ticker, "30D %")
    if r5 is None or r30 is None or pd.isna(r5) or pd.isna(r30):
        return "Market data pending"
    r5 = float(r5)
    r30 = float(r30)
    if r5 > 5 and r30 > 0:
        return "Accumulation / positive reaction"
    if r5 > 3 and r30 < 0:
        return "Rebound from weak base"
    if r5 < -5 and r30 < 0:
        return "Risk-off / weak positioning"
    if abs(r5) <= 3:
        return "Muted positioning"
    return "Mixed positioning"


def _meaning_for_event(row: dict[str, object]) -> str:
    ticker = str(row.get("ticker", ""))
    target = str(row.get("target", ""))
    positioning = str(row.get("market_positioning", ""))
    if ticker == "NXTC" and "SIM0505" in str(row.get("asset", "")):
        if "weak" in positioning.lower() or "risk-off" in positioning.lower():
            return (
                "NXTC is in a pre-catalyst window, but the stock is not yet showing convincing accumulation. "
                "This means the upcoming SIM0505/CDH6 data remain important, but the market is not currently paying ahead of the event."
            )
        if "accumulation" in positioning.lower() or "positive" in positioning.lower():
            return (
                "NXTC is in a pre-catalyst window and price action suggests investors may be positioning ahead of SIM0505/CDH6 data."
            )
        return (
            "NXTC is in a pre-catalyst window, but price action is still muted. The key question is whether investors begin accumulating ahead of SIM0505/CDH6 data."
        )
    if str(row.get("read_through", "")) in {"High", "Medium-High"}:
        return f"Read-through monitor: strength or weakness here can influence how investors value the broader {target} ADC category."
    if str(row.get("read_through", "")) == "Separate channel":
        return "Separate asset lane: useful for partnering optionality, but not part of the core ovarian ADC readout."
    return "Context monitor: useful for broader capital appetite, but not a direct NXTC catalyst."


def catalyst_events_to_table(return_table: pd.DataFrame | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for event in CATALYST_EVENTS:
        record = {
            "ticker": event.ticker,
            "company": event.company,
            "title": event.title,
            "category": event.category,
            "expected_timing": event.expected_timing,
            "asset": event.asset,
            "target": event.target,
            "indication": event.indication,
            "impact": event.impact,
            "read_through": event.read_through,
            "status": event.status,
            "source_note": event.source_note,
            "source_url": event.source_url,
        }
        record["phase"] = _infer_phase(pd.Series(record))
        record["market_positioning"] = _positioning_label(event.ticker, return_table)
        record["priority_score"] = round(IMPACT_SCORE.get(event.impact, 1) + READ_SCORE.get(event.read_through, 1), 2)
        record["what_it_means"] = _meaning_for_event(record)
        rows.append(record)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values(["priority_score", "ticker"], ascending=[False, True]).reset_index(drop=True)


def summarize_catalysts(table: pd.DataFrame) -> CatalystSummary:
    if table.empty:
        return CatalystSummary(
            total_events=0,
            high_impact_events=0,
            primary_events=0,
            highest_priority="No curated catalysts loaded",
            ingestion_note="Manual catalyst file is empty; future ingestion hook remains available.",
        )
    high = int((table["impact"] == "High").sum())
    primary = int((table["read_through"] == "Primary").sum())
    top = table.iloc[0]
    nxtc = table[(table["ticker"] == "NXTC") & (table["read_through"] == "Primary")]
    if not nxtc.empty:
        primary_row = nxtc.iloc[0]
        primary_phase = str(primary_row["phase"])
        primary_positioning = str(primary_row["market_positioning"])
        primary_meaning = str(primary_row["what_it_means"])
    else:
        primary_phase = "Unavailable"
        primary_positioning = "Unavailable"
        primary_meaning = "No primary NXTC catalyst found in curated table."
    return CatalystSummary(
        total_events=int(len(table)),
        high_impact_events=high,
        primary_events=primary,
        highest_priority=f"{top['ticker']}: {top['title']}",
        ingestion_note=(
            "Catalysts are curated in v0.6, but the schema is intentionally ready for automated ingestion. "
            "Do not rely on manual curation long-term."
        ),
        primary_phase=primary_phase,
        primary_positioning=primary_positioning,
        primary_meaning=primary_meaning,
    )


def build_catalyst_readout(table: pd.DataFrame, summary: CatalystSummary) -> list[str]:
    if table.empty:
        return [summary.ingestion_note]
    insights = [
        f"Catalyst phase: {summary.primary_phase}. This tells us where NXTC sits relative to its main event window.",
        f"Positioning: {summary.primary_positioning}. This is based on recent stock behavior, not the clinical quality of the asset.",
        "Meaning: " + summary.primary_meaning,
    ]
    nxtc = table[(table["ticker"] == "NXTC") & (table["read_through"] == "Primary")]
    if not nxtc.empty:
        top_nxtc = nxtc.iloc[0]
        insights.append(
            f"Primary event to explain clearly: {top_nxtc['asset']} targeting {top_nxtc['target']} in {top_nxtc['indication']} ({top_nxtc['expected_timing']})."
        )
    direct = table[table["read_through"].isin(["High", "Medium-High", "Primary"])]
    direct_peers = sorted({str(t) for t in direct["ticker"].tolist() if str(t) != "NXTC"})
    if direct_peers:
        insights.append("Read-through monitor list: " + ", ".join(direct_peers) + ". These are not all direct competitors; they help measure ADC/target appetite.")
    insights.append(summary.ingestion_note)
    return insights


def build_catalyst_intelligence_cards(table: pd.DataFrame, summary: CatalystSummary) -> list[dict[str, str]]:
    if table.empty:
        return [{"label": "Catalyst Layer", "value": "Unavailable", "caption": summary.ingestion_note}]
    support = []
    nxtc = table[(table["ticker"] == "NXTC") & (table["read_through"] == "Primary")]
    if not nxtc.empty:
        support.append(str(nxtc.iloc[0]["expected_timing"]))
        support.append(str(nxtc.iloc[0]["target"]))
    return [
        {"label": "Catalyst Phase", "value": summary.primary_phase, "caption": "Where NXTC sits relative to its primary event window"},
        {"label": "Positioning", "value": summary.primary_positioning, "caption": "Recent price action around the catalyst setup"},
        {"label": "Support Signals", "value": " · ".join(support) if support else "Monitoring", "caption": "Primary event context"},
        {"label": "Catalyst Risk", "value": "Fade / exhaustion", "caption": "Watch acceleration into event window versus early sell-the-news behavior"},
    ]


def ingestion_backlog_table() -> pd.DataFrame:
    return pd.DataFrame(future_ingestion_backlog())
