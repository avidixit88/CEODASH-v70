"""Channel-level analysis for direct peers, ADC landscape, and side-channel baskets.

v0.7 clarity refactor:
- distinguishes short-term momentum, medium trend, and quarterly regime
- explains 90D strength/weakness instead of burying it behind a blended label
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

import pandas as pd

from config.peer_channels import PEER_COMPANIES
from engines.relative_performance_engine import safe_return

CHANNEL_LABELS = {
    "cdh6_ovarian_adc": "CDH6 / Ovarian ADC",
    "b7h4_adc": "B7-H4 ADC",
    "ovarian_cancer": "Ovarian Cancer",
    "adc_capital_flow": "ADC Capital Flow",
    "small_cap_oncology": "Small-Cap Oncology",
    "alzheimers_partnering_channel": "Alzheimer's Side Channel",
    "bone_disease_partnering_channel": "Bone Disease Side Channel",
}

CHANNEL_ORDER = [
    "cdh6_ovarian_adc",
    "b7h4_adc",
    "ovarian_cancer",
    "adc_capital_flow",
    "small_cap_oncology",
    "alzheimers_partnering_channel",
    "bone_disease_partnering_channel",
]


@dataclass(frozen=True)
class ChannelSummary:
    channel: str
    label: str
    tickers: tuple[str, ...]
    avg_5d: float | None
    avg_30d: float | None
    avg_60d: float | None
    avg_90d: float | None
    momentum_label: str
    capital_flow: str
    best_ticker: str | None
    worst_ticker: str | None
    timeframe_story: str
    interpretation: str


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None and not pd.isna(v)]
    return round(mean(clean), 2) if clean else None


def _bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    if value >= 5:
        return "Strong"
    if value <= -5:
        return "Weak"
    return "Neutral"


def _label(avg_5d: float | None, avg_30d: float | None, avg_90d: float | None) -> tuple[str, str, str, str]:
    short = _bucket(avg_5d)
    medium = _bucket(avg_30d)
    quarter = _bucket(avg_90d)

    if quarter == "Strong" and short == "Weak":
        headline = "Strong quarter, short-term pullback"
        flow = "Longer-term inflow, recent fade"
        interp = "Capital has rewarded this lane over the quarter, but recent momentum has cooled."
    elif quarter == "Weak" and short == "Strong":
        headline = "Weak quarter, short-term rebound"
        flow = "Rebound from weak base"
        interp = "Recent strength may be a bounce, but sustained capital commitment is not yet proven."
    elif short == "Strong" and medium in {"Strong", "Neutral"}:
        headline = "Improving"
        flow = "Selective inflow"
        interp = "Recent buying is improving the lane; watch whether it persists into the 30D trend."
    elif short == "Weak" and medium in {"Weak", "Neutral"}:
        headline = "Softening"
        flow = "Selective outflow"
        interp = "Recent pressure is weighing on the lane; read-through support is limited right now."
    elif quarter == "Strong":
        headline = "Quarterly strength"
        flow = "Longer-term inflow"
        interp = "The lane has been rewarded over the quarter, even if the near-term tape is not decisive."
    elif quarter == "Weak":
        headline = "Quarterly pressure"
        flow = "Longer-term outflow"
        interp = "The lane has not attracted sustained capital over the quarter."
    else:
        headline = "Neutral"
        flow = "No clear flow"
        interp = "No strong capital-flow signal yet; avoid over-reading one short-term move."

    story = f"5D {short} / 30D {medium} / 90D {quarter}"
    return headline, flow, story, interp


def analyze_channels(return_table: pd.DataFrame) -> tuple[list[ChannelSummary], pd.DataFrame]:
    summaries: list[ChannelSummary] = []
    table_rows: list[dict[str, object]] = []

    for channel in CHANNEL_ORDER:
        tickers = sorted({company.ticker for company in PEER_COMPANIES if channel in company.channels and company.ticker != "NXTC"})
        if not tickers:
            continue
        rows = []
        for ticker in tickers:
            r5 = safe_return(return_table, ticker, "5D %")
            r30 = safe_return(return_table, ticker, "30D %")
            r60 = safe_return(return_table, ticker, "60D %")
            r90 = safe_return(return_table, ticker, "90D %")
            rows.append((ticker, r5, r30, r60, r90))

        avg_5d = _avg([r[1] for r in rows])
        avg_30d = _avg([r[2] for r in rows])
        avg_60d = _avg([r[3] for r in rows])
        avg_90d = _avg([r[4] for r in rows])
        momentum, flow, story, interpretation = _label(avg_5d, avg_30d, avg_90d)

        ranked = [r for r in rows if r[1] is not None]
        ranked.sort(key=lambda x: x[1], reverse=True)
        best = ranked[0][0] if ranked else None
        worst = ranked[-1][0] if ranked else None

        label = CHANNEL_LABELS.get(channel, channel)
        summaries.append(ChannelSummary(channel, label, tuple(tickers), avg_5d, avg_30d, avg_60d, avg_90d, momentum, flow, best, worst, story, interpretation))
        table_rows.append({
            "Channel": label,
            "Tickers": ", ".join(tickers),
            "5D Avg %": avg_5d,
            "30D Avg %": avg_30d,
            "60D Avg %": avg_60d,
            "90D Avg %": avg_90d,
            "Timeframe Read": story,
            "Headline": momentum,
            "Capital Flow": flow,
            "Interpretation": interpretation,
            "Best 5D": best or "N/A",
            "Weakest 5D": worst or "N/A",
        })

    return summaries, pd.DataFrame(table_rows)
