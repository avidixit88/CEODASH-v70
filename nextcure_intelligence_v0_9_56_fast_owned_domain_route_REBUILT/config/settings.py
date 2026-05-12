"""Application-level settings.

Keep client-facing controls minimal. Operational options belong here or in
backend configuration, not in the CEO dashboard surface.
"""

APP_TITLE = "NextCure Intelligence System"
APP_SUBTITLE = "Market Positioning + Catalyst Intelligence"
APP_VERSION = "v0.9.47 Evidence Route Fallback"
COMPANY_TICKER = "NXTC"
PRIMARY_COLOR = "#7C3AED"
BACKGROUND_GRADIENT = "linear-gradient(135deg, #0B1020 0%, #111827 42%, #1E1B4B 100%)"
TECHNICAL_LOOKBACK_MONTHS = 6

# Manual catalyst records are acceptable for v1, but this product should not
# depend on hand curation long-term. The ingestion backend is intentionally
# scaffolded so press-release feeds, SEC/IR pages, ClinicalTrials.gov, conference
# abstract pages, or licensed APIs can populate the same schema later.
CATALYST_INGESTION_MODE = "manual_v1_with_future_scraper_hook"

CLINICAL_TRIALS_INGESTION_MODE = "live_pull_each_run_with_future_database_hook"
