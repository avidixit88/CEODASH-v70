from dataclasses import dataclass


@dataclass(frozen=True)
class FreshSignal:
    category: str
    signal: str
    relevance: str
    implication: str
    action: str


def build_fresh_signals():
    """Return real external signals only.

    The prior prototype used manually seeded patent/grant/funding placeholders.
    Those are intentionally removed so the executive buckets only receive
    information from live/real lanes or existing market-data engines.
    Future patent, grant, PubMed, and funding modules should append here only
    after they perform real ingestion.
    """
    return []
