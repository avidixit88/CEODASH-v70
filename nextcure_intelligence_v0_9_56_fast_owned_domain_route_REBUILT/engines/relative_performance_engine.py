"""Relative performance calculations for NextCure market positioning."""

from __future__ import annotations

import pandas as pd

# Trading-day windows. 30D/60D/90D are explicit because the CEO readout
# needs to distinguish shorter-term momentum from medium-term trend quality.
RETURN_WINDOWS = {
    "1D %": 1,
    "5D %": 5,
    "30D %": 30,
    "60D %": 60,
    "90D %": 90,
}


def pct_return(df: pd.DataFrame, trading_days: int) -> float | None:
    clean = df.dropna(subset=["Close"])
    if len(clean) <= trading_days:
        return None
    current = float(clean["Close"].iloc[-1])
    prior = float(clean["Close"].iloc[-(trading_days + 1)])
    if prior == 0:
        return None
    return ((current / prior) - 1.0) * 100.0


def build_return_table(prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker, df in prices.items():
        row: dict[str, object] = {"Ticker": ticker}
        for label, days in RETURN_WINDOWS.items():
            value = pct_return(df, days)
            row[label] = round(value, 2) if value is not None else None
        row["Last Close"] = round(float(df["Close"].iloc[-1]), 2) if not df.empty else None
        row["Rows"] = len(df)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("Ticker").reset_index(drop=True)


def build_relative_index(prices: dict[str, pd.DataFrame], tickers: list[str]) -> pd.DataFrame:
    """Normalize each ticker to 0% from its first shared date."""
    series: list[pd.DataFrame] = []
    for ticker in tickers:
        df = prices.get(ticker)
        if df is None or df.empty:
            continue
        item = df[["Date", "Close"]].copy()
        item = item.rename(columns={"Close": ticker})
        series.append(item)

    if not series:
        return pd.DataFrame(columns=["Date"])

    merged = series[0]
    for item in series[1:]:
        merged = merged.merge(item, on="Date", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["Date"])

    for ticker in [col for col in merged.columns if col != "Date"]:
        first = float(merged[ticker].iloc[0])
        merged[ticker] = ((merged[ticker] / first) - 1.0) * 100.0 if first else 0.0
    return merged


def classify_vs_benchmark(subject_return: float | None, benchmark_return: float | None, threshold: float = 3.0) -> str:
    if subject_return is None or benchmark_return is None:
        return "Unavailable"
    spread = subject_return - benchmark_return
    if spread > threshold:
        return "Outperforming"
    if spread < -threshold:
        return "Underperforming"
    return "Tracking"


def safe_return(return_table: pd.DataFrame, ticker: str, window: str) -> float | None:
    row = return_table.loc[return_table["Ticker"] == ticker]
    if row.empty:
        return None
    value = row.iloc[0].get(window)
    if value is None or pd.isna(value):
        return None
    return float(value)
