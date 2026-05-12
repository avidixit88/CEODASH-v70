"""Chart builders for the Streamlit UI."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


CHART_BG = "rgba(15,23,42,.35)"
GRID = "rgba(255,255,255,.08)"
FONT = "#F8FAFC"
LEGEND_FONT = "#FFFFFF"


def _apply_dark_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 20, "r": 20, "t": 35, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=CHART_BG,
        font={"color": FONT},
        legend={"orientation": "h", "y": 1.06, "x": 0, "font": {"color": LEGEND_FONT, "size": 12}, "bgcolor": "rgba(15,23,42,.45)", "bordercolor": "rgba(255,255,255,.10)", "borderwidth": 1},
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def relative_performance_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for ticker in ["NXTC", "XBI", "QQQ"]:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[ticker],
                mode="lines",
                name=ticker,
                line={"width": 3 if ticker == "NXTC" else 2},
            )
        )
    fig = _apply_dark_layout(fig, 420)
    fig.update_yaxes(title_text="Relative Performance %")
    fig.update_xaxes(title_text=None)
    return fig


def peer_bar_chart(peer_df: pd.DataFrame) -> go.Figure:
    view = peer_df.sort_values("5D %", ascending=True).tail(12)
    fig = go.Figure(
        go.Bar(
            x=view["5D %"],
            y=view["Ticker"],
            orientation="h",
            text=view["Read"],
            textposition="auto",
        )
    )
    fig = _apply_dark_layout(fig, 420)
    fig.update_xaxes(title_text="5D Performance %")
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig


def peer_timeframe_comparison_chart(peer_df: pd.DataFrame) -> go.Figure:
    """Clear peer landscape chart using 5D / 30D / 90D side-by-side bars.

    This replaces the older single 5D momentum bar, which was too hard to
    interpret because it did not explain whether a move was short-term noise or
    part of a broader trend.
    """
    if peer_df is None or peer_df.empty:
        return _apply_dark_layout(go.Figure(), 420)
    df = peer_df.copy()
    # Keep the view focused and deterministic: NXTC first, then most relevant
    # movers by absolute 30D/90D action.
    for col in ["5D %", "30D %", "90D %"]:
        if col not in df.columns:
            df[col] = None
    df["_priority"] = df["Ticker"].eq("NXTC").map({True: 10_000, False: 0})
    df["_move"] = df[["5D %", "30D %", "90D %"]].abs().max(axis=1, skipna=True).fillna(0)
    view = df.sort_values(["_priority", "_move"], ascending=[False, False]).head(12)
    # Reverse so horizontal bars read top-to-bottom in priority order.
    view = view.iloc[::-1]
    y = view["Ticker"] + " · " + view["Company"].astype(str).str.slice(0, 22)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=view["5D %"], y=y, orientation="h", name="5D", opacity=0.92))
    fig.add_trace(go.Bar(x=view["30D %"], y=y, orientation="h", name="30D", opacity=0.82))
    fig.add_trace(go.Bar(x=view["90D %"], y=y, orientation="h", name="90D", opacity=0.72))
    fig.add_vline(x=0, line_width=1, line_color="rgba(255,255,255,.45)")
    fig = _apply_dark_layout(fig, 520)
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Return by timeframe %", zeroline=True, zerolinecolor="rgba(255,255,255,.45)")
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig


def technical_stock_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Six-month stock technical panel: price/EMAs, RSI, MACD."""
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.055,
        row_heights=[0.58, 0.20, 0.22],
        subplot_titles=(f"{ticker} Six-Month Price Structure", "RSI 14", "MACD"),
    )
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="OHLC"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA20"], mode="lines", name="EMA 20", line={"width": 1.8}), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA50"], mode="lines", name="EMA 50", line={"width": 1.8}), row=1, col=1)
    if "EMA200" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["EMA200"], mode="lines", name="EMA 200", line={"width": 1.4, "dash": "dot"}), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI14"], mode="lines", name="RSI 14", line={"width": 2}), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", opacity=0.35, row=2, col=1)
    fig.add_hline(y=50, line_dash="dot", opacity=0.20, row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", opacity=0.35, row=2, col=1)
    fig.add_trace(go.Bar(x=df["Date"], y=df["MACD_Hist"], name="MACD Hist", opacity=0.55), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], mode="lines", name="MACD", line={"width": 2}), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD_Signal"], mode="lines", name="Signal", line={"width": 1.6}), row=3, col=1)
    fig.update_layout(
        height=760,
        margin={"l": 20, "r": 20, "t": 55, "b": 25},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=CHART_BG,
        font={"color": FONT},
        legend={"orientation": "h", "y": 1.03, "x": 0, "font": {"color": LEGEND_FONT, "size": 12}, "bgcolor": "rgba(15,23,42,.45)", "bordercolor": "rgba(255,255,255,.10)", "borderwidth": 1},
        xaxis_rangeslider_visible=False,
    )
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    return fig


def channel_momentum_chart(channel_df: pd.DataFrame) -> go.Figure:
    if channel_df.empty:
        return _apply_dark_layout(go.Figure(), 420)
    view = channel_df.sort_values("30D Avg %", ascending=True, na_position="first")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=view["30D Avg %"], y=view["Channel"], orientation="h", name="30D Avg %"))
    fig.add_trace(go.Scatter(x=view["5D Avg %"], y=view["Channel"], mode="markers", name="5D Avg %", marker={"size": 11}))
    fig = _apply_dark_layout(fig, 440)
    fig.update_xaxes(title_text="Channel Performance %")
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig


def capital_flow_chart(flow_df: pd.DataFrame) -> go.Figure:
    if flow_df.empty:
        return _apply_dark_layout(go.Figure(), 420)
    view = flow_df.sort_values("Capital Score", ascending=True, na_position="first")
    fig = go.Figure(
        go.Bar(
            x=view["Capital Score"],
            y=view["Channel"],
            orientation="h",
            text=view["Posture"],
            textposition="auto",
        )
    )
    fig = _apply_dark_layout(fig, 430)
    fig.update_xaxes(title_text="Capital Flow Score")
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig


def catalyst_priority_chart(catalyst_df: pd.DataFrame) -> go.Figure:
    if catalyst_df.empty:
        return _apply_dark_layout(go.Figure(), 420)
    view = catalyst_df.sort_values("priority_score", ascending=True).tail(10)
    labels = view["ticker"] + " · " + view["asset"]
    fig = go.Figure(
        go.Bar(
            x=view["priority_score"],
            y=labels,
            orientation="h",
            text=view["impact"],
            textposition="auto",
        )
    )
    fig = _apply_dark_layout(fig, 430)
    fig.update_xaxes(title_text="Catalyst Priority Score")
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig


def technical_setup_chart(technical_df: pd.DataFrame) -> go.Figure:
    if technical_df is None or technical_df.empty:
        return _apply_dark_layout(go.Figure(), 420)
    view = technical_df.sort_values("Setup Score", ascending=True).tail(14)
    fig = go.Figure(
        go.Bar(
            x=view["Setup Score"],
            y=view["Ticker"],
            orientation="h",
            text=view["Setup State"],
            textposition="auto",
        )
    )
    fig = _apply_dark_layout(fig, 430)
    fig.update_xaxes(title_text="Technical Setup Score (0-10)", range=[0, 10])
    fig.update_yaxes(title_text=None, gridcolor="rgba(255,255,255,.04)")
    return fig
