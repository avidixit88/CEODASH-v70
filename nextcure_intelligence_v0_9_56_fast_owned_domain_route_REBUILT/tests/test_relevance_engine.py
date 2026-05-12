from engines.relevance_engine import build_relevance_intelligence


def test_relevance_engine_scores_nextcure_specific_signals():
    summary = build_relevance_intelligence()
    assert summary.headline
    assert not summary.signal_table.empty
    assert not summary.theme_table.empty
    assert not summary.query_map.empty
    assert "Score" in summary.signal_table.columns
    assert summary.signal_table["Score"].max() >= 5
    assert any("CDH6" in str(v) or "B7-H4" in str(v) for v in summary.signal_table["Matched Terms"])
    assert summary.next_questions
