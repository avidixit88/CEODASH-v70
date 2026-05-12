"""Mock datasets for Iteration 1/2 UI prototyping.

These are deliberately deterministic so visual audits and future regression
checks are stable. Replace with real market-data adapters in Iteration 3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.tickers import BENCHMARKS, FEATURED_TECHNICAL_TICKERS, PEER_GROUPS, TECHNICAL_LOOKBACK_DAYS


def build_mock_performance(days: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    curves = {
        "NXTC": np.cumsum(rng.normal(0.12, 0.85, len(dates))),
        "XBI": np.cumsum(rng.normal(0.04, 0.45, len(dates))),
        "QQQ": np.cumsum(rng.normal(0.02, 0.30, len(dates))),
    }
    df = pd.DataFrame({"Date": dates})
    for ticker, values in curves.items():
        df[ticker] = values - values[0]
    return df


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd, signal, hist


def build_mock_technical_data(days: int = TECHNICAL_LOOKBACK_DAYS) -> dict[str, pd.DataFrame]:
    """Create six-month price, RSI, and MACD mock data for featured tickers."""
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    technicals: dict[str, pd.DataFrame] = {}
    base_profiles = {
        "NXTC": (1.35, 0.0020, 0.040, 101),
        "XBI": (92.0, 0.0005, 0.012, 202),
        "QQQ": (445.0, 0.0008, 0.010, 303),
        "MRSN": (5.10, 0.0015, 0.035, 404),
        "PYXS": (3.80, -0.0002, 0.040, 505),
        "CTMX": (2.45, 0.0009, 0.045, 606),
    }
    for ticker in FEATURED_TECHNICAL_TICKERS:
        start, drift, vol, seed = base_profiles.get(ticker, (10.0, 0.0005, 0.025, 707))
        rng = np.random.default_rng(seed)
        shocks = rng.normal(drift, vol, len(dates))
        cycle = 0.018 * np.sin(np.linspace(0, 5 * np.pi, len(dates)))
        close = start * np.exp(np.cumsum(shocks + cycle / len(dates)))
        high = close * (1 + rng.uniform(0.003, 0.030, len(dates)))
        low = close * (1 - rng.uniform(0.003, 0.030, len(dates)))
        open_ = close * (1 + rng.normal(0, 0.010, len(dates)))
        volume = rng.integers(120_000, 3_500_000, len(dates))
        df = pd.DataFrame({
            "Date": dates,
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        })
        df["RSI14"] = _rsi(df["Close"], 14)
        df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = _macd(df["Close"])
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
        technicals[ticker] = df
    return technicals


def build_mock_peer_table() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(7)
    for group, tickers in PEER_GROUPS.items():
        for ticker in tickers:
            one_week = rng.normal(1.2, 5.5)
            one_month = one_week + rng.normal(2.0, 8.0)
            signal = "Risk-On" if one_week > 3 else "Neutral" if one_week > -3 else "Pressure"
            rows.append(
                {
                    "Group": group,
                    "Ticker": ticker,
                    "5D %": round(one_week, 2),
                    "30D %": round(one_month, 2),
                    "Read": signal,
                }
            )
    return pd.DataFrame(rows)


def build_mock_kpi_cards() -> list[dict[str, str]]:
    return [
        {"label": "NXTC 30D Relative to XBI", "value": "+6.8%", "tone": "positive"},
        {"label": "Biotech Tape", "value": "Constructive", "tone": "positive"},
        {"label": "NXTC Technical Posture", "value": "Base / Improving", "tone": "positive"},
        {"label": "Capital Window", "value": "Selective", "tone": "neutral"},
    ]


def build_mock_insights() -> list[str]:
    return [
        "NXTC is currently modeled as outperforming XBI over the prototype lookback window, suggesting potential stock-specific interest rather than purely sector-driven movement.",
        "The six-month technical layer adds price, RSI, and MACD context so leadership can see whether relative performance is being supported by actual trend structure or short-lived volatility.",
        "ADC and oncology platform peers show uneven but improving momentum, which supports a selective rather than broad risk-on interpretation.",
    ]
