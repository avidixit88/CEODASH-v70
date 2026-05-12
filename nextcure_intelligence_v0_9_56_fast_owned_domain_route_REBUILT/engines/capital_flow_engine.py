"""Capital-flow interpretation engine built on channel summaries.

v0.7 clarity refactor: the score is still available, but the language explains
whether capital is favoring a lane now, over the quarter, or not at all.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engines.channel_engine import ChannelSummary


@dataclass(frozen=True)
class CapitalFlowSummary:
    strongest_channel: str
    weakest_channel: str
    adc_posture: str
    ovarian_posture: str
    divergence_note: str


def _score(channel: ChannelSummary) -> float:
    vals = []
    for value, weight in [(channel.avg_5d, 0.30), (channel.avg_30d, 0.30), (channel.avg_90d, 0.40)]:
        if value is not None and not pd.isna(value):
            vals.append(float(value) * weight)
    return round(sum(vals), 2) if vals else float("nan")


def _posture_from_channel(channel: ChannelSummary | None) -> str:
    if channel is None:
        return "Unavailable"
    return channel.capital_flow


def build_capital_flow_table(channels: list[ChannelSummary]) -> pd.DataFrame:
    rows = []
    for channel in channels:
        score = _score(channel)
        rows.append({
            "Channel": channel.label,
            "Capital Score": score if not pd.isna(score) else None,
            "Posture": channel.capital_flow,
            "Timeframe Read": channel.timeframe_story,
            "Interpretation": channel.interpretation,
            "5D Avg %": channel.avg_5d,
            "30D Avg %": channel.avg_30d,
            "90D Avg %": channel.avg_90d,
            "Best 5D": channel.best_ticker or "N/A",
            "Weakest 5D": channel.worst_ticker or "N/A",
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Capital Score", ascending=False, na_position="last").reset_index(drop=True)


def summarize_capital_flow(channels: list[ChannelSummary], flow_table: pd.DataFrame) -> CapitalFlowSummary:
    if flow_table.empty:
        return CapitalFlowSummary("Unavailable", "Unavailable", "Unavailable", "Unavailable", "No channel data available.")
    strongest = str(flow_table.iloc[0]["Channel"])
    weakest = str(flow_table.iloc[-1]["Channel"])
    channel_by_key = {c.channel: c for c in channels}
    adc = channel_by_key.get("adc_capital_flow")
    ovarian = channel_by_key.get("ovarian_cancer")
    cdh6 = channel_by_key.get("cdh6_ovarian_adc")

    adc_score = _score(adc) if adc else float("nan")
    ovarian_score = _score(ovarian) if ovarian else float("nan")
    cdh6_score = _score(cdh6) if cdh6 else float("nan")

    divergence_note = "Capital flow does not show a clean divergence across monitored channels."
    if adc and ovarian and adc_score - ovarian_score >= 4:
        divergence_note = "Capital is favoring ADCs more than ovarian-specific names, so modality appetite is stronger than indication appetite."
    elif adc and ovarian and ovarian_score - adc_score >= 4:
        divergence_note = "Capital is favoring ovarian cancer more than the broader ADC basket, suggesting indication-specific interest."
    if cdh6 and not pd.isna(cdh6_score) and cdh6_score < adc_score - 4:
        divergence_note = "Broader ADC appetite is stronger than CDH6/ovarian ADC specifically; NXTC may not be benefiting from targeted inflows into its core thesis yet."

    return CapitalFlowSummary(strongest, weakest, _posture_from_channel(adc), _posture_from_channel(ovarian), divergence_note)


def build_capital_flow_insights(summary: CapitalFlowSummary) -> list[str]:
    return [
        f"Capital is strongest in: {summary.strongest_channel}.",
        f"Capital is weakest in: {summary.weakest_channel}.",
        f"ADC lane: {summary.adc_posture}; ovarian lane: {summary.ovarian_posture}.",
        "Meaning: " + summary.divergence_note,
    ]
