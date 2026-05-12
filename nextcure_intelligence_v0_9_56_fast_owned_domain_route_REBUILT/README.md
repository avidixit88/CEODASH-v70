# NextCure Intelligence Dashboard v0.9.47

Key changes in v0.9.47:
- Evidence route isolation: RSS/fast-news failures no longer stop company-site/newsroom fallback.
- Focus-company trace now records fast-news failure while continuing to company-site routing.
- Preserves observational NextCure trace behavior, no ClinicalTrials.gov sponsor hardcoding.

# NextCure Intelligence Dashboard v0.9.44

Precision-lane ClinicalTrials.gov discovery plus generic company-site evidence routing.

Key changes in v0.9.44:
- Pivoted ClinicalTrials.gov discovery away from broad oncology crawling into precision lanes: CDH6 ovarian ADC, B7-H4 ADC, and ovarian/fallopian/peritoneal ADC.
- Removed default broad ADC Oncology query specs so sponsor/entity volume stays smaller and evidence checks can go deeper.
- Preserved sponsor-agnostic discovery: sponsors are still extracted from ClinicalTrials.gov payloads, not hardcoded into discovery.
- Expanded evidence routing beyond public-company tickers and IR pages to company news, press, media, events, science, publications, pipeline, and conference pages.
- Private companies and non-IR website structures are now eligible for the company-site evidence route.
- Preserved publication-freshness vs catalyst/event-timing separation and stale-catalyst suppression.

Audit: 26 regression tests passing.

# NextCure Intelligence System — v0.9.32 Adaptive Outcome Evidence

This build refines the first real external intelligence lane: ClinicalTrials.gov.

## What changed

- Removed manually seeded/pseudo patent, grant, and funding placeholders from the executive flow.
- Kept ClinicalTrials.gov as the first real live external source.
- Rewrote ClinicalTrials.gov synthesis so the four executive buckets receive interpreted reads instead of raw source-count language.
- Improved usefulness of the trial lane by emphasizing direct-lane activity, active sponsor/phase density, repeated trial-design language, ovarian ADC activity, side-channel reads, and positioning implications.
- Preserved the future database hook via `persistence_payload`.
- No Streamlit cache was added; each run performs a fresh lightweight pull.

## Audit

- Python compile check
- Pytest suite
- Direct analysis smoke test
- ZIP integrity check

## v0.9.36 dynamic sponsor-discovery patch

This patch upgrades the ClinicalTrials.gov intelligence layer from a narrow one-page signal pull into a bounded discovery system:

- Expands CDH6, B7-H4, ovarian ADC, gynecologic ADC, and broader ADC query terms with target/program aliases.
- Uses larger page sizes and bounded pagination so the backend can discover more sponsors before executive filtering.
- Adds `engines/sponsor_discovery_engine.py` to build a dynamic sponsor registry from ClinicalTrials.gov lead sponsors and collaborators.
- Normalizes sponsor names so subsidiaries/legal variants collapse into one sponsor entity.
- Updates sponsor evidence routing so static ticker mappings are optional enrichment only, not the gatekeeper for who gets discovered.
- Preserves unmapped/private/academic sponsors in a drill-down table with generated evidence-search links for IR/press release follow-up.
- Feeds the sponsor discovery and evidence status back into the Executive Summary four-question board through the existing clinical signal path.

Audit run: `PYTHONPATH=. pytest -q` passed with 10 tests.



## v0.9.39 Catalyst Intelligence + Evidence Freshness Rebuild

This build upgrades the sponsor-evidence layer from shallow headline matching into a freshness-aware catalyst intelligence pass.

Key changes:
- Suppresses stale/expired conference headlines, such as prior-year AACR/ASCO signals, from the executive summary.
- Preserves stale matches in a separate audit table instead of silently deleting them.
- Adds catalyst classes, freshness states, source quality, and confidence labels to sponsor evidence.
- Adds sponsor evidence coverage audit: sponsors discovered, sponsors searched, raw items seen, active signals accepted, stale items suppressed, and low-lane relevance items rejected.
- Condenses large sponsor lists by sponsor tier instead of dumping dozens of names into Question #3.
- Adds strict/adjacent/category lane precision language so broad ovarian ADC activity does not masquerade as CDH6-specific evidence.
- Expands sponsor evidence capacity to reduce the chance that late-discovered sponsors are pushed out by earlier mapped names.

BuildWell standard applied: discover broadly, rank selectively, suppress stale catalyst noise, and show the audit trail.

## v0.9.38 Recall-First ClinicalTrials.gov Discovery

This build replaces the prior owned-program guardrail patch with a sponsor-agnostic, recall-first ClinicalTrials.gov discovery layer. Discovery now runs by target, condition, intervention/modality, title/acronym, and broad ADC context rather than by hardcoded sponsor. Sponsors are extracted only after trials are surfaced from ClinicalTrials.gov payloads.

Key additions:
- Multi-family ClinicalTrials.gov query expansion across `query.term`, `query.intr`, `query.titles`, and `query.cond`.
- Bounded pagination with page-cap diagnostics.
- Per-query discovery audit table showing fetched records, retained records, available totals, search area, query family, and truncation state.
- NCT-level deduplication that preserves discovery provenance and matched relevance fields.
- Trial table now includes query family, matched fields, relevance score, and discovery provenance.
- Sponsor registry remains dynamic: sponsors and collaborators are extracted from discovered trial records, not predefined as the discovery source.

Build audit: `PYTHONPATH=. pytest -q` → 12 passed.


## v0.9.47 Evidence Route Fallback
- Added generic sponsor IR/newsroom discovery without hardcoded company URLs.
- Parses recent release titles/dates from likely IR/news-release pages and routes them through the existing freshness, catalyst, data-stage, and lane-overlap classifier.
- Preserves ticker/news fallback and fast-screen audit while adding `generic_ir_newsroom_discovery` as a first-class source route.

## v0.9.42 Fast-Screen Promotion + Sponsor-Grade Prioritization

- Repairs fast-screen promotion so sponsor-scoped recent data/result/presentation headlines can promote into evidence classification.
- Adds sponsor-grade prioritization before the runtime evidence budget so company-like sponsors are screened ahead of hospitals, academic centers, and consortium/site entities.
- Expands the fast-screen cap with shorter per-source timeouts while preserving bounded dashboard runtime.
- Adds focus-company screen status to the evidence audit so NextCure is reported as screened, accepted, missed, or not present instead of silently disappearing.
- Keeps publication freshness separate from catalyst/event timing.
