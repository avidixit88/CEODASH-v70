"""Application orchestration layer.

The public UI still calls run_prototype_analysis() for backward compatibility,
but Iteration 3 now routes through real market data when available.
"""

from __future__ import annotations

from engines.real_analysis_runner import AnalysisResults, run_real_analysis


def run_prototype_analysis() -> AnalysisResults:
    return run_real_analysis()
