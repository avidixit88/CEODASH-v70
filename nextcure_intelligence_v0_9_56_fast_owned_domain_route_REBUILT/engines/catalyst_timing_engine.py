"""Catalyst timing and relative event-map engine for v0.8."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class CatalystTimingSummary:
    nxtc_primary_event: str
    nxtc_timing: str
    nxtc_asset: str
    nxtc_target: str
    peer_timing_read: str
    timing_interpretation: str
    timeline_table: pd.DataFrame


def _timing_bucket(expected: str) -> tuple[str, int]:
    e = (expected or "").lower()
    if "asco" in e or "q2 2026" in e:
        return "Near-term / defined", 1
    if "2026" in e:
        return "2026 / broad window", 2
    if "ongoing" in e:
        return "Ongoing read-through", 3
    if "future" in e or "partner" in e:
        return "Future / dependent", 4
    return "Timing unclear", 5


def build_catalyst_timing_summary(catalyst_table: pd.DataFrame | None) -> CatalystTimingSummary:
    if catalyst_table is None or catalyst_table.empty:
        empty = pd.DataFrame(columns=["Ticker", "Company", "Asset", "Target", "Timing", "Timing Bucket", "Read-through", "Event"])
        return CatalystTimingSummary(
            nxtc_primary_event="Unavailable",
            nxtc_timing="Unavailable",
            nxtc_asset="Unavailable",
            nxtc_target="Unavailable",
            peer_timing_read="Peer catalyst timing unavailable.",
            timing_interpretation="Catalyst timing could not be evaluated because the catalyst table is empty.",
            timeline_table=empty,
        )

    rows = []
    for _, row in catalyst_table.iterrows():
        bucket, rank = _timing_bucket(str(row.get("expected_timing", "")))
        rows.append({
            "Ticker": row.get("ticker", ""),
            "Company": row.get("company", ""),
            "Asset": row.get("asset", ""),
            "Target": row.get("target", ""),
            "Timing": row.get("expected_timing", ""),
            "Timing Bucket": bucket,
            "Timing Rank": rank,
            "Read-through": row.get("read_through", ""),
            "Impact": row.get("impact", ""),
            "Event": row.get("title", ""),
        })
    timeline = pd.DataFrame(rows).sort_values(["Timing Rank", "Ticker"]).reset_index(drop=True)

    nxtc = catalyst_table[(catalyst_table["ticker"] == "NXTC") & (catalyst_table["read_through"] == "Primary")]
    if nxtc.empty:
        primary = catalyst_table[catalyst_table["ticker"] == "NXTC"].head(1)
    else:
        primary = nxtc.head(1)
    if primary.empty:
        nxtc_event = "No primary NXTC catalyst loaded"
        nxtc_timing = "Unavailable"
        nxtc_asset = "Unavailable"
        nxtc_target = "Unavailable"
    else:
        p = primary.iloc[0]
        nxtc_event = str(p.get("title", ""))
        nxtc_timing = str(p.get("expected_timing", ""))
        nxtc_asset = str(p.get("asset", ""))
        nxtc_target = str(p.get("target", ""))

    direct_peers = timeline[(timeline["Ticker"] != "NXTC") & (timeline["Read-through"].isin(["High", "Medium-High", "Primary"]))]
    near_peers = direct_peers[direct_peers["Timing Rank"] <= 2]
    if not near_peers.empty:
        peer_timing_read = "Several direct read-through peers also have 2026 catalyst visibility."
    elif not direct_peers.empty:
        peer_timing_read = "Peer events are mostly ongoing read-through rather than a clearly defined near-term catalyst."
    else:
        peer_timing_read = "No high read-through peer catalyst timing is currently loaded."

    if "asco" in nxtc_timing.lower() or "q2" in nxtc_timing.lower():
        timing_interpretation = (
            f"NXTC has a defined near-term catalyst: {nxtc_asset} ({nxtc_target}) at {nxtc_timing}. "
            "This should be shown separately from general peer momentum because it can create pre-event positioning even when the broader sector is weak."
        )
    else:
        timing_interpretation = (
            "NXTC catalyst timing is not yet specific enough to anchor a near-term positioning window. "
            "The dashboard should treat peer/sector strength as context, not as a direct event clock."
        )

    return CatalystTimingSummary(
        nxtc_primary_event=nxtc_event,
        nxtc_timing=nxtc_timing,
        nxtc_asset=nxtc_asset,
        nxtc_target=nxtc_target,
        peer_timing_read=peer_timing_read,
        timing_interpretation=timing_interpretation,
        timeline_table=timeline.drop(columns=["Timing Rank"], errors="ignore"),
    )
