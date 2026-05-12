"""Smoke tests for adaptive activation language.

These are intentionally simple branch tests. They confirm that the operator
recommendation changes when the underlying market data flips from weak to strong.
"""

from __future__ import annotations

import pandas as pd

from engines.activation_engine import build_activation_summary
from engines.classification_engine import ClassificationResult
from engines.technical_engine import TechnicalSnapshot


def _returns(nxtc_5d: float, nxtc_30d: float, xbi_5d: float, xbi_30d: float) -> pd.DataFrame:
    return pd.DataFrame([
        {"Ticker": "NXTC", "5D %": nxtc_5d, "30D %": nxtc_30d},
        {"Ticker": "XBI", "5D %": xbi_5d, "30D %": xbi_30d},
    ])


def _classification(spread_5d: float, spread_30d: float, market: str) -> ClassificationResult:
    return ClassificationResult(
        market_regime=market,
        market_meaning="test",
        nxtc_vs_xbi="test",
        nxtc_vs_qqq="test",
        driver="test",
        short_term_state="test",
        medium_term_state="test",
        quarterly_state="test",
        overall_posture="test",
        plain_english_summary="test",
        spread_5d_xbi=spread_5d,
        spread_30d_xbi=spread_30d,
        spread_60d_xbi=spread_30d,
        spread_90d_xbi=spread_30d,
    )


def _technical(score: float) -> TechnicalSnapshot:
    return TechnicalSnapshot("NXTC", 1.0, 50.0, 0.0, 1.0, "test", "test", "test", "test", "test", score, "test", [], [], {})


def test_weak_pre_catalyst_generates_attention_gap_language() -> None:
    out = build_activation_summary(
        _returns(-11, -7, -2, 6),
        _classification(-9, -13, "Biotech Weak"),
        _technical(4.3),
        "Pre-catalyst",
        "Risk-off / weak positioning",
        "Quarterly strength",
        "Weak",
    )
    assert out.market_attention == "Low"
    assert "Underdeveloped" in out.activation_state
    assert "weak_relative_performance" in out.triggered_paths
    assert "attention gap" in " ".join(out.recommended_actions).lower()


def test_strong_attention_does_not_reuse_attention_gap_first_action() -> None:
    out = build_activation_summary(
        _returns(12, 20, 1, 3),
        _classification(11, 17, "Biotech Strong"),
        _technical(7.8),
        "Pre-catalyst",
        "Constructive positioning",
        "Strong inflow",
        "Strong",
    )
    assert out.market_attention == "High"
    assert "already paying attention" in out.activation_state.lower()
    assert "attention gap" not in out.recommended_actions[0].lower()
    assert "high_attention_branch" in out.triggered_paths
