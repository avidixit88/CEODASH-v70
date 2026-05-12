"""Classification layer for CEO-readable market positioning labels.

v0.7 clarity refactor:
- separates momentum (5D), trend (30D/60D), and quarterly regime (90D)
- uses a smaller vocabulary: Strong / Neutral / Weak plus clear qualifiers
- avoids misleading labels such as "balanced" when 90D is very strong or very weak
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engines.relative_performance_engine import safe_return


@dataclass(frozen=True)
class ClassificationResult:
    market_regime: str
    market_meaning: str
    nxtc_vs_xbi: str
    nxtc_vs_qqq: str
    driver: str
    short_term_state: str
    medium_term_state: str
    quarterly_state: str
    overall_posture: str
    plain_english_summary: str
    spread_5d_xbi: float | None
    spread_30d_xbi: float | None
    spread_60d_xbi: float | None
    spread_90d_xbi: float | None


def _spread(return_table: pd.DataFrame, a: str, b: str, window: str) -> float | None:
    av = safe_return(return_table, a, window)
    bv = safe_return(return_table, b, window)
    if av is None or bv is None:
        return None
    return av - bv


def _bucket(value: float | None, pos: float = 3.0, neg: float = -3.0) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    if value >= pos:
        return "Strong"
    if value <= neg:
        return "Weak"
    return "Neutral"


def _relative_label(spread: float | None, threshold: float = 3.0) -> str:
    if spread is None:
        return "Unavailable"
    if spread > threshold:
        return "Outperforming"
    if spread < -threshold:
        return "Underperforming"
    return "Tracking"


def _market_regime(xbi_5d: float | None, qqq_5d: float | None, xbi_30d: float | None) -> tuple[str, str]:
    if xbi_5d is None or qqq_5d is None:
        return "Unavailable", "Market context could not be read because benchmark data is incomplete."
    spread = xbi_5d - qqq_5d
    if xbi_5d < -2 and spread < -2:
        return "Biotech Weak", "Biotech is weaker than the broader growth market, creating a headwind for small-cap oncology stories."
    if xbi_5d > 2 and spread > 2:
        return "Biotech Strong", "Biotech is outperforming the broader growth market, which can support risk-taking in development-stage names."
    if xbi_30d is not None and xbi_30d < -5:
        return "Biotech Soft", "The recent week is mixed, but the 30D biotech trend is still soft."
    if xbi_30d is not None and xbi_30d > 5:
        return "Biotech Constructive", "The recent week is mixed, but the 30D biotech trend remains constructive."
    return "Mixed", "Biotech is not giving a clean risk-on or risk-off signal right now."


def _driver(spread_5d: float | None, spread_30d: float | None) -> str:
    if spread_5d is None:
        return "Unavailable"
    if abs(spread_5d) <= 1.5 and (spread_30d is None or abs(spread_30d) <= 3):
        return "Sector-driven"
    if spread_5d > 3 or (spread_30d is not None and spread_30d > 5):
        return "Stock-specific strength"
    if spread_5d < -3 or (spread_30d is not None and spread_30d < -5):
        return "Stock-specific weakness"
    return "Mixed"


def _timeframe_state(spread: float | None, label: str) -> str:
    b = _bucket(spread)
    if b == "Strong":
        return f"{label} Strong"
    if b == "Weak":
        return f"{label} Weak"
    if b == "Neutral":
        return f"{label} Neutral"
    return f"{label} Unavailable"


def _overall(short: str, medium: str, quarter: str) -> str:
    weak_count = sum("Weak" in x for x in [short, medium, quarter])
    strong_count = sum("Strong" in x for x in [short, medium, quarter])
    if weak_count >= 2 and strong_count == 0:
        return "Weak across most timeframes"
    if strong_count >= 2 and weak_count == 0:
        return "Strong across most timeframes"
    if "Quarterly Strong" in quarter and "Short-Term Weak" in short:
        return "Strong quarter, short-term pullback"
    if "Quarterly Weak" in quarter and "Short-Term Strong" in short:
        return "Weak quarter, short-term rebound"
    if weak_count and strong_count:
        return "Mixed by timeframe"
    return "Mostly neutral / tracking"


def classify_market_position(return_table: pd.DataFrame) -> ClassificationResult:
    xbi_5d = safe_return(return_table, "XBI", "5D %")
    qqq_5d = safe_return(return_table, "QQQ", "5D %")
    xbi_30d = safe_return(return_table, "XBI", "30D %")

    spread_5d = _spread(return_table, "NXTC", "XBI", "5D %")
    spread_30d = _spread(return_table, "NXTC", "XBI", "30D %")
    spread_60d = _spread(return_table, "NXTC", "XBI", "60D %")
    spread_90d = _spread(return_table, "NXTC", "XBI", "90D %")
    qqq_spread_5d = _spread(return_table, "NXTC", "QQQ", "5D %")

    market, market_meaning = _market_regime(xbi_5d, qqq_5d, xbi_30d)
    short = _timeframe_state(spread_5d, "Short-Term")
    medium = _timeframe_state(spread_30d, "Medium-Term")
    quarter = _timeframe_state(spread_90d, "Quarterly")
    posture = _overall(short, medium, quarter)

    relative = _relative_label(spread_5d)
    driver = _driver(spread_5d, spread_30d)
    if "Weak" in posture:
        summary = "NXTC is not currently being rewarded versus XBI; the market needs a catalyst or visible reversal to change the narrative."
    elif "Strong" in posture:
        summary = "NXTC is being rewarded versus XBI; the market appears more willing to differentiate the story."
    elif "Mixed" in posture:
        summary = "NXTC is sending mixed signals: one timeframe is improving while another remains pressured."
    else:
        summary = "NXTC is mostly tracking the sector; company-specific differentiation is not yet clear."

    return ClassificationResult(
        market_regime=market,
        market_meaning=market_meaning,
        nxtc_vs_xbi=relative,
        nxtc_vs_qqq=_relative_label(qqq_spread_5d),
        driver=driver,
        short_term_state=short,
        medium_term_state=medium,
        quarterly_state=quarter,
        overall_posture=posture,
        plain_english_summary=summary,
        spread_5d_xbi=spread_5d,
        spread_30d_xbi=spread_30d,
        spread_60d_xbi=spread_60d,
        spread_90d_xbi=spread_90d,
    )
