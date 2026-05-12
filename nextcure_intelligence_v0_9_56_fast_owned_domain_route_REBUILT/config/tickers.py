"""Ticker and peer configuration for the NextCure Intelligence System.

Iteration 0.2 intentionally uses mock data. These groups give the UI real
structure and will become the source of truth when market data is wired in.
"""

BENCHMARKS = {
    "NextCure": "NXTC",
    "Biotech ETF": "XBI",
    "Nasdaq Proxy": "QQQ",
}

PEER_GROUPS = {
    "ADC / Oncology Platform Peers": ["MRSN", "PYXS", "SBTX", "CTMX", "ZNTL"],
    "Target / Modality Watchlist": ["CGON", "ALX", "IMAB", "BCYC", "FATE"],
    "Small-Cap Oncology Capital Market Set": ["ORIC", "KURA", "ERAS", "IKNA", "TERN"],
}

FEATURED_TECHNICAL_TICKERS = ["NXTC", "XBI", "QQQ", "MRSN", "PYXS", "CTMX"]
DEFAULT_LOOKBACK_DAYS = 30
TECHNICAL_LOOKBACK_DAYS = 126
