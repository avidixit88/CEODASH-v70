"""Market data engine for Iteration 3.

The MVP uses yfinance because it is fast to prototype, free, and simple to
swap out later for a licensed market-data provider. The UI should not call
this module directly; orchestration stays in prototype_runner.py for now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

try:
    import yfinance as yf
except Exception:  # pragma: no cover - handled at runtime for graceful app boot
    yf = None


REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


@dataclass(frozen=True)
class MarketDataBundle:
    prices: dict[str, pd.DataFrame]
    failures: dict[str, str] = field(default_factory=dict)
    fetched_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "yfinance"

    @property
    def ok_tickers(self) -> list[str]:
        return sorted(self.prices.keys())

    @property
    def failed_tickers(self) -> list[str]:
        return sorted(self.failures.keys())


def _normalize_history(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        # Defensive normalization in case a multi-ticker object leaks through.
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Prefer adjusted close semantics by using Close returned by auto_adjust=True.
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")

    df = df.loc[:, list(REQUIRED_COLUMNS)].dropna(subset=["Close"])
    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "Date"})
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    for col in REQUIRED_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df.sort_values("Date").reset_index(drop=True)


def fetch_single_ticker(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch one ticker with a narrow, auditable return contract."""
    if yf is None:
        raise RuntimeError("yfinance is not installed. Run `pip install -r requirements.txt`.")

    history = yf.Ticker(ticker).history(
        period=period,
        interval=interval,
        auto_adjust=True,
        actions=False,
        raise_errors=False,
    )
    df = _normalize_history(history)
    if df.empty:
        raise ValueError("no usable price history returned")
    return df


def fetch_market_data(
    tickers: Iterable[str],
    period: str = "6mo",
    interval: str = "1d",
    min_rows: int = 30,
) -> MarketDataBundle:
    """Fetch multiple tickers and preserve partial success.

    A single failed ticker should never kill the dashboard.
    """
    prices: dict[str, pd.DataFrame] = {}
    failures: dict[str, str] = {}

    for raw_ticker in tickers:
        ticker = raw_ticker.strip().upper()
        if not ticker:
            continue
        try:
            df = fetch_single_ticker(ticker, period=period, interval=interval)
            if len(df) < min_rows:
                raise ValueError(f"insufficient rows: {len(df)} < {min_rows}")
            prices[ticker] = df
        except Exception as exc:  # noqa: BLE001 - preserve reason for audit panel
            failures[ticker] = str(exc)

    return MarketDataBundle(prices=prices, failures=failures)


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add standard six-month technical indicators for the stock detail view."""
    out = df.copy()
    close = out["Close"].astype(float)

    out["EMA20"] = close.ewm(span=20, adjust=False).mean()
    out["EMA50"] = close.ewm(span=50, adjust=False).mean()
    out["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, pd.NA)
    out["RSI14"] = (100 - (100 / (1 + rs))).fillna(50).clip(0, 100)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_Signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"] = out["MACD"] - out["MACD_Signal"]
    return out
