"""CEO-level insight generation from classifications and channel analytics.

v0.7 clarity refactor:
- interpretation first, numbers second
- compresses noisy lines into a small executive readout
- uses timeframe hierarchy instead of blended labels
"""

from __future__ import annotations

import pandas as pd

from engines.channel_engine import ChannelSummary
from engines.classification_engine import ClassificationResult
from engines.relative_performance_engine import safe_return


def _fmt(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:+.1f}%"


def _nxtc_line(return_table: pd.DataFrame, classification: ClassificationResult) -> str:
    n5 = safe_return(return_table, "NXTC", "5D %")
    n30 = safe_return(return_table, "NXTC", "30D %")
    n90 = safe_return(return_table, "NXTC", "90D %")
    return (
        f"NXTC posture: {classification.overall_posture}. "
        f"The stock is {classification.nxtc_vs_xbi.lower()} XBI in the short term, and the driver reads as {classification.driver.lower()}. "
        f"Support: NXTC 5D {_fmt(n5)}, 30D {_fmt(n30)}, 90D {_fmt(n90)}; "
        f"vs XBI spreads are 5D {_fmt(classification.spread_5d_xbi)}, 30D {_fmt(classification.spread_30d_xbi)}, 90D {_fmt(classification.spread_90d_xbi)}."
    )


def _channel_line(channel: ChannelSummary) -> str:
    return (
        f"{channel.label}: {channel.momentum_label}. "
        f"{channel.interpretation} "
        f"Read: {channel.timeframe_story} "
        f"(5D {_fmt(channel.avg_5d)}, 30D {_fmt(channel.avg_30d)}, 90D {_fmt(channel.avg_90d)}). "
        f"Best recent contributor: {channel.best_ticker or 'N/A'}."
    )


def build_executive_insights(
    return_table: pd.DataFrame,
    classification: ClassificationResult,
    channels: list[ChannelSummary],
    failures: dict[str, str],
) -> list[str]:
    insights: list[str] = []

    insights.append(f"Market environment: {classification.market_regime}. {classification.market_meaning}")
    insights.append(_nxtc_line(return_table, classification))
    insights.append(f"Plain-English takeaway: {classification.plain_english_summary}")

    channel_map = {c.channel: c for c in channels}
    for key in ["cdh6_ovarian_adc", "b7h4_adc", "adc_capital_flow", "ovarian_cancer"]:
        channel = channel_map.get(key)
        if channel:
            insights.append(_channel_line(channel))

    if failures:
        insights.append(
            f"Data quality note: {len(failures)} ticker(s) were unavailable or incomplete and were skipped safely. This does not break the dashboard, but it can slightly distort channel averages."
        )

    return insights or ["Real market data loaded, but benchmark history was insufficient to produce a complete readout."]


def build_watch_items(classification: ClassificationResult, channels: list[ChannelSummary]) -> list[dict[str, str]]:
    direct = {c.channel: c for c in channels}
    watch_items = [
        {"label": "Market", "value": classification.market_regime, "caption": "Biotech vs broader market"},
        {"label": "NXTC Posture", "value": classification.overall_posture, "caption": "5D / 30D / 90D hierarchy"},
        {"label": "Driver", "value": classification.driver, "caption": "Sector vs stock-specific"},
        {"label": "Quarter", "value": classification.quarterly_state, "caption": "90D view"},
    ]
    adc = direct.get("adc_capital_flow")
    ovarian = direct.get("ovarian_cancer")
    if adc:
        watch_items.append({"label": "ADC Flow", "value": adc.momentum_label, "caption": adc.timeframe_story})
    if ovarian:
        watch_items.append({"label": "Ovarian Lane", "value": ovarian.momentum_label, "caption": ovarian.timeframe_story})
    return watch_items
