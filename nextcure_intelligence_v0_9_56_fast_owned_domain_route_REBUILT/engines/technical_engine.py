"""Advanced technical intelligence engine for v0.8.

This layer translates price/volume/RSI/MACD structure into CEO-readable setup
language. It is intentionally not a trading recommendation engine; it explains
whether the stock appears technically weak, stabilizing, improving, or extended.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isnan

import pandas as pd


@dataclass(frozen=True)
class TechnicalSnapshot:
    ticker: str
    close: float | None
    rsi14: float | None
    macd_hist: float | None
    volume_ratio: float | None
    trend_state: str
    momentum_state: str
    accumulation_state: str
    exhaustion_state: str
    setup_state: str
    setup_score: float
    interpretation: str
    confirmation_signals: list[str]
    risk_signals: list[str]
    components: dict[str, float]


def _safe_last(df: pd.DataFrame, col: str) -> float | None:
    if col not in df.columns or df.empty:
        return None
    val = pd.to_numeric(df[col], errors="coerce").dropna()
    if val.empty:
        return None
    out = float(val.iloc[-1])
    return None if isnan(out) else out


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return (a / b - 1.0) * 100.0


def _trend_state(df: pd.DataFrame) -> tuple[str, float, list[str], list[str]]:
    close = _safe_last(df, "Close")
    ema20 = _safe_last(df, "EMA20")
    ema50 = _safe_last(df, "EMA50")
    ema200 = _safe_last(df, "EMA200")
    confirmations: list[str] = []
    risks: list[str] = []
    score = 5.0

    if close is None or ema20 is None or ema50 is None:
        return "Trend unavailable", 5.0, confirmations, ["Insufficient price history for trend read"]

    above20 = close >= ema20
    above50 = close >= ema50
    above200 = ema200 is not None and close >= ema200
    ema_stack_bull = ema200 is not None and ema20 >= ema50 >= ema200
    ema_stack_bear = ema200 is not None and ema20 <= ema50 <= ema200

    dist20 = _pct(close, ema20) or 0.0
    dist50 = _pct(close, ema50) or 0.0

    if above20 and above50 and (above200 or ema200 is None) and ema_stack_bull:
        state = "Strong trend"
        score = 8.5
        confirmations.append("Price is above key moving averages with a constructive EMA stack")
    elif above20 and (dist50 > -3 or above50):
        state = "Early uptrend / reclaim attempt"
        score = 6.6
        confirmations.append("Price has reclaimed the short-term trend line")
        if not above50:
            risks.append("Still needs to reclaim EMA50 for stronger confirmation")
    elif not above20 and not above50 and ema_stack_bear:
        if dist20 > -6 and dist50 > -12:
            state = "Downtrend, base attempt"
            score = 4.2
            confirmations.append("Price is still weak, but not deeply disconnected from EMA20")
            risks.append("Price remains below EMA20/EMA50")
        else:
            state = "Downtrend"
            score = 2.8
            risks.append("Price remains below key moving averages")
    elif not above20 and above50:
        state = "Pullback within broader trend"
        score = 5.8
        confirmations.append("Price remains above EMA50 despite short-term weakness")
    else:
        state = "Base forming / neutral structure"
        score = 5.1
        confirmations.append("Price structure is not clearly breaking down or breaking out")

    return state, score, confirmations, risks


def _momentum_state(df: pd.DataFrame) -> tuple[str, float, list[str], list[str]]:
    rsi = _safe_last(df, "RSI14")
    hist = _safe_last(df, "MACD_Hist")
    confirmations: list[str] = []
    risks: list[str] = []
    score = 5.0
    state = "Momentum neutral"

    hist_series = pd.to_numeric(df.get("MACD_Hist", pd.Series(dtype=float)), errors="coerce").dropna()
    rsi_series = pd.to_numeric(df.get("RSI14", pd.Series(dtype=float)), errors="coerce").dropna()
    hist_slope = None
    if len(hist_series) >= 6:
        hist_slope = float(hist_series.iloc[-1] - hist_series.iloc[-6])

    if rsi is None or hist is None:
        return "Momentum unavailable", score, confirmations, ["Insufficient RSI/MACD history"]

    if rsi < 30:
        confirmations.append("RSI is deeply oversold, which can create bounce potential")
        score += 0.8
    elif rsi < 40:
        confirmations.append("RSI is weak but near a range where stabilization can begin")
        score += 0.3
    elif rsi > 65:
        risks.append("RSI is elevated; upside may be more extended")
        score -= 0.4

    if hist_slope is not None and hist < 0 and hist_slope > 0:
        state = "Bottoming momentum"
        score += 1.2
        confirmations.append("MACD histogram is still negative but improving")
    elif hist_slope is not None and hist > 0 and hist_slope > 0:
        state = "Building momentum"
        score += 1.8
        confirmations.append("MACD histogram is positive and expanding")
    elif hist_slope is not None and hist > 0 and hist_slope < 0:
        state = "Momentum cooling"
        score -= 0.6
        risks.append("MACD momentum is positive but fading")
    elif hist_slope is not None and hist < 0 and hist_slope < 0:
        state = "Weakening momentum"
        score -= 1.1
        risks.append("MACD histogram is negative and deteriorating")

    if len(rsi_series) >= 6:
        rsi_delta = float(rsi_series.iloc[-1] - rsi_series.iloc[-6])
        if rsi_delta > 4:
            confirmations.append("RSI has improved over the last week")
            score += 0.4
        elif rsi_delta < -4:
            risks.append("RSI has weakened over the last week")
            score -= 0.4

    return state, max(0.0, min(10.0, score)), confirmations, risks


def _accumulation_state(df: pd.DataFrame) -> tuple[str, float, list[str], list[str]]:
    confirmations: list[str] = []
    risks: list[str] = []
    if len(df) < 25 or "Volume" not in df.columns:
        return "Accumulation unavailable", 5.0, confirmations, ["Insufficient volume history"]

    close = pd.to_numeric(df["Close"], errors="coerce")
    volume = pd.to_numeric(df["Volume"], errors="coerce")
    vol20 = volume.rolling(20, min_periods=10).mean()
    last_vol_ratio = float(volume.iloc[-1] / vol20.iloc[-1]) if vol20.iloc[-1] else 1.0
    last10 = df.tail(10).copy()
    last10["up_day"] = close.tail(10).diff() > 0
    up_vol = pd.to_numeric(last10.loc[last10["up_day"], "Volume"], errors="coerce").mean()
    down_vol = pd.to_numeric(last10.loc[~last10["up_day"], "Volume"], errors="coerce").mean()
    score = 5.0

    if pd.notna(up_vol) and pd.notna(down_vol) and down_vol > 0 and up_vol / down_vol > 1.15:
        confirmations.append("Up days are attracting more volume than down days")
        score += 1.6
    elif pd.notna(up_vol) and pd.notna(down_vol) and down_vol > 0 and up_vol / down_vol < 0.85:
        risks.append("Down days are carrying more volume than up days")
        score -= 1.2

    if last_vol_ratio > 1.4 and close.iloc[-1] > close.iloc[-2]:
        confirmations.append("Latest up move came with above-average volume")
        score += 1.2
    elif last_vol_ratio > 1.4 and close.iloc[-1] < close.iloc[-2]:
        risks.append("Latest weakness came with above-average volume")
        score -= 1.2

    recent_range = (pd.to_numeric(df["High"], errors="coerce") - pd.to_numeric(df["Low"], errors="coerce")) / close.replace(0, pd.NA)
    if len(recent_range.dropna()) >= 20:
        range10 = float(recent_range.tail(10).mean())
        range30 = float(recent_range.tail(30).mean()) if len(recent_range) >= 30 else range10
        if range10 < range30 * 0.82:
            confirmations.append("Volatility is compressing, which can precede a directional move")
            score += 0.7

    if score >= 6.7:
        state = "Accumulation signs emerging"
    elif score <= 3.8:
        state = "Distribution / weak sponsorship"
    else:
        state = "Accumulation not confirmed"
    return state, max(0.0, min(10.0, score)), confirmations, risks


def _exhaustion_state(df: pd.DataFrame) -> tuple[str, float, list[str], list[str]]:
    confirmations: list[str] = []
    risks: list[str] = []
    if len(df) < 35:
        return "Exhaustion unavailable", 5.0, confirmations, []
    close = pd.to_numeric(df["Close"], errors="coerce")
    rsi = pd.to_numeric(df.get("RSI14", pd.Series(dtype=float)), errors="coerce")
    hist = pd.to_numeric(df.get("MACD_Hist", pd.Series(dtype=float)), errors="coerce")
    score = 5.0

    c_now, c_prev = float(close.iloc[-1]), float(close.iloc[-15])
    r_now, r_prev = float(rsi.iloc[-1]), float(rsi.iloc[-15])
    h_now, h_prev = float(hist.iloc[-1]), float(hist.iloc[-8])

    if c_now < c_prev and r_now > r_prev + 2:
        confirmations.append("Bullish RSI divergence: price is lower while RSI is improving")
        score += 1.5
    if c_now > c_prev and r_now < r_prev - 2:
        risks.append("Bearish RSI divergence: price is higher while RSI is weakening")
        score -= 1.5
    if h_now < h_prev and h_now > 0:
        risks.append("MACD histogram is rolling over from positive territory")
        score -= 0.8

    if score >= 6.4:
        state = "Seller exhaustion possible"
    elif score <= 3.8:
        state = "Upside exhaustion risk"
    else:
        state = "No clear exhaustion signal"
    return state, max(0.0, min(10.0, score)), confirmations, risks


def analyze_ticker_technical(ticker: str, df: pd.DataFrame) -> TechnicalSnapshot:
    trend, trend_score, tc, tr = _trend_state(df)
    momentum, momentum_score, mc, mr = _momentum_state(df)
    accumulation, accumulation_score, ac, ar = _accumulation_state(df)
    exhaustion, exhaustion_score, ec, er = _exhaustion_state(df)

    score = round(
        trend_score * 0.32
        + momentum_score * 0.28
        + accumulation_score * 0.24
        + exhaustion_score * 0.16,
        1,
    )
    if score >= 7.2:
        setup_state = "Constructive setup"
        interpretation = "Technicals are improving with enough confirmation to treat the setup as constructive."
    elif score >= 6.0:
        setup_state = "Improving setup"
        interpretation = "Technical conditions are improving, but the stock still needs confirmation before the market has conviction."
    elif score >= 4.4:
        setup_state = "Unconfirmed / watch setup"
        interpretation = "There are mixed technical signals. The stock may be stabilizing, but confirmation is not strong enough yet."
    else:
        setup_state = "Weak setup"
        interpretation = "Technicals remain weak; the burden of proof is on buyers to show accumulation and momentum improvement."

    return TechnicalSnapshot(
        ticker=ticker,
        close=_safe_last(df, "Close"),
        rsi14=_safe_last(df, "RSI14"),
        macd_hist=_safe_last(df, "MACD_Hist"),
        volume_ratio=None,
        trend_state=trend,
        momentum_state=momentum,
        accumulation_state=accumulation,
        exhaustion_state=exhaustion,
        setup_state=setup_state,
        setup_score=score,
        interpretation=interpretation,
        confirmation_signals=(tc + mc + ac + ec)[:6],
        risk_signals=(tr + mr + ar + er)[:6],
        components={
            "Trend": round(trend_score, 1),
            "Momentum": round(momentum_score, 1),
            "Accumulation": round(accumulation_score, 1),
            "Exhaustion": round(exhaustion_score, 1),
        },
    )


def build_technical_table(technicals: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for ticker, df in technicals.items():
        snap = analyze_ticker_technical(ticker, df)
        rows.append({
            "Ticker": ticker,
            "Setup Score": snap.setup_score,
            "Setup State": snap.setup_state,
            "Trend": snap.trend_state,
            "Momentum": snap.momentum_state,
            "Accumulation": snap.accumulation_state,
            "Exhaustion": snap.exhaustion_state,
            "RSI14": None if snap.rsi14 is None else round(snap.rsi14, 1),
            "Close": None if snap.close is None else round(snap.close, 2),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("Setup Score", ascending=False).reset_index(drop=True)


def build_peer_technical_read(technical_table: pd.DataFrame) -> list[str]:
    if technical_table.empty or "NXTC" not in technical_table["Ticker"].values:
        return ["Peer technical comparison is unavailable because NXTC or peer data is incomplete."]
    nxtc = technical_table[technical_table["Ticker"] == "NXTC"].iloc[0]
    peers = technical_table[~technical_table["Ticker"].isin(["NXTC", "XBI", "QQQ"])]
    if peers.empty:
        return ["NXTC technicals are available, but peer technical comparison is not available yet."]
    peer_avg = float(peers["Setup Score"].mean())
    spread = float(nxtc["Setup Score"]) - peer_avg
    if spread >= 1.0:
        rel = "stronger than the peer technical average"
    elif spread <= -1.0:
        rel = "weaker than the peer technical average"
    else:
        rel = "roughly in line with the peer technical average"
    leader = peers.sort_values("Setup Score", ascending=False).iloc[0]
    laggard = peers.sort_values("Setup Score", ascending=True).iloc[0]
    return [
        f"NXTC is {rel}: NXTC {float(nxtc['Setup Score']):.1f}/10 vs peer average {peer_avg:.1f}/10.",
        f"Strongest peer setup: {leader['Ticker']} ({float(leader['Setup Score']):.1f}/10, {leader['Setup State']}).",
        f"Weakest peer setup: {laggard['Ticker']} ({float(laggard['Setup Score']):.1f}/10, {laggard['Setup State']}).",
    ]
