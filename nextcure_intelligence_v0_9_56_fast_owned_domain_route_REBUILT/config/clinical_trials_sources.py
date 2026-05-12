"""ClinicalTrials.gov precision-lane query universe.

v0.9.44 pivot: the clinical-trials lane should not behave like a universal
oncology crawler. It should search narrowly and deeply around the biologically
relevant battlefield that matters to the executive dashboard:

- CDH6 / cadherin-6 ovarian ADC activity;
- B7-H4 / VTCN1 ADC and gynecologic activity;
- ovarian / fallopian / primary-peritoneal antibody-drug conjugates.

The discovery layer remains sponsor-agnostic. Sponsors are extracted from the
trial payloads after retrieval. Static sponsor/ticker maps are enrichment aids
only; they do not decide which sponsors exist.

Design choices:
- precision lane queries first, broad context removed from the default run;
- structured ClinicalTrials.gov search areas where possible;
- bounded pagination and NCT dedupe downstream;
- query provenance retained for auditability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClinicalTrialSearchSpec:
    label: str
    query: str
    strategic_lane: str
    priority: int
    query_area: str = "term"  # term | cond | intr | titles | spons
    max_pages: int = 2
    query_family: str = "broad_term"
    retain_any_terms: tuple[str, ...] = ()


# Sponsor-agnostic precision searches. No company names are used as discovery
# inputs. Program/target aliases are allowed because they define biology/assets,
# not sponsor identity.
CLINICAL_TRIAL_SEARCH_SPECS: tuple[ClinicalTrialSearchSpec, ...] = (
    # CDH6 / cadherin-6 target/program discovery.
    ClinicalTrialSearchSpec(
        label="CDH6 / Ovarian ADC",
        query='(CDH6 OR "cadherin 6" OR "cadherin-6" OR "DS-6000" OR "DS-6000a" OR "raludotatug deruxtecan" OR "R-DXd") AND (ovarian OR "fallopian tube" OR "primary peritoneal" OR gynecologic OR gynaecologic OR "solid tumor")',
        strategic_lane="Direct pipeline / ovarian ADC relevance",
        priority=1,
        query_area="term",
        max_pages=3,
        query_family="precision_target_disease_term",
        retain_any_terms=("cdh6", "cadherin", "ds-6000", "raludotatug", "r-dxd", "adc", "antibody-drug", "ovarian", "fallopian", "peritoneal", "gynecologic", "gynaecologic"),
    ),
    ClinicalTrialSearchSpec(
        label="CDH6 / Ovarian ADC",
        query='CDH6 OR "cadherin 6" OR "cadherin-6" OR "DS-6000" OR "DS-6000a" OR "raludotatug deruxtecan" OR "R-DXd"',
        strategic_lane="Direct pipeline / ovarian ADC relevance",
        priority=1,
        query_area="intr",
        max_pages=2,
        query_family="precision_intervention_target",
        retain_any_terms=("cdh6", "cadherin", "ds-6000", "raludotatug", "r-dxd", "adc", "antibody-drug", "ovarian", "gynecologic"),
    ),
    ClinicalTrialSearchSpec(
        label="CDH6 / Ovarian ADC",
        query='CDH6 OR "cadherin 6" OR "cadherin-6" OR "DS-6000" OR "DS-6000a" OR "raludotatug"',
        strategic_lane="Direct pipeline / ovarian ADC relevance",
        priority=1,
        query_area="titles",
        max_pages=2,
        query_family="precision_title_target",
        retain_any_terms=("cdh6", "cadherin", "ds-6000", "raludotatug", "adc", "ovarian", "gynecologic"),
    ),

    # B7-H4 adjacent target discovery.
    ClinicalTrialSearchSpec(
        label="B7-H4 ADC",
        query='("B7-H4" OR "B7H4" OR "VTCN1" OR "B7x" OR "B7S1") AND (ADC OR "antibody drug conjugate" OR "antibody-drug conjugate" OR ovarian OR gynecologic OR gynaecologic OR "solid tumor")',
        strategic_lane="Direct target-adjacent competitive relevance",
        priority=1,
        query_area="term",
        max_pages=3,
        query_family="precision_target_modality_term",
        retain_any_terms=("b7-h4", "b7h4", "vtcn1", "b7x", "b7s1", "adc", "antibody-drug", "ovarian", "gynecologic", "gynaecologic"),
    ),
    ClinicalTrialSearchSpec(
        label="B7-H4 ADC",
        query='"B7-H4" OR "B7H4" OR "VTCN1" OR "B7x" OR "B7S1"',
        strategic_lane="Direct target-adjacent competitive relevance",
        priority=1,
        query_area="intr",
        max_pages=2,
        query_family="precision_intervention_target",
        retain_any_terms=("b7-h4", "b7h4", "vtcn1", "b7x", "b7s1", "adc", "antibody-drug", "ovarian", "gynecologic"),
    ),
    ClinicalTrialSearchSpec(
        label="B7-H4 ADC",
        query='"B7-H4" OR "B7H4" OR "VTCN1"',
        strategic_lane="Direct target-adjacent competitive relevance",
        priority=1,
        query_area="titles",
        max_pages=2,
        query_family="precision_title_target",
        retain_any_terms=("b7-h4", "b7h4", "vtcn1", "adc", "ovarian", "gynecologic"),
    ),

    # Ovarian/fallopian/peritoneal ADC category discovery. These are the broadest
    # default searches, but they are still disease + modality constrained.
    ClinicalTrialSearchSpec(
        label="Ovarian ADC",
        query='("ovarian cancer" OR "ovarian carcinoma" OR "platinum-resistant ovarian" OR "fallopian tube cancer" OR "primary peritoneal cancer") AND (ADC OR "antibody drug conjugate" OR "antibody-drug conjugate" OR "folate receptor" OR "FR alpha" OR "FRα" OR TROP2 OR HER2 OR NaPi2b OR CDH6 OR "B7-H4" OR B7H4)',
        strategic_lane="Ovarian ADC category momentum",
        priority=2,
        query_area="term",
        max_pages=3,
        query_family="precision_disease_modality_term",
        retain_any_terms=("ovarian", "fallopian", "peritoneal", "adc", "antibody-drug", "conjugate", "folate", "fr alpha", "frα", "trop2", "her2", "napi2b", "cdh6", "b7-h4", "b7h4"),
    ),
    ClinicalTrialSearchSpec(
        label="Ovarian ADC",
        query='"ovarian cancer" OR "ovarian carcinoma" OR "platinum-resistant ovarian" OR "fallopian tube cancer" OR "primary peritoneal cancer"',
        strategic_lane="Ovarian ADC category momentum",
        priority=2,
        query_area="cond",
        max_pages=2,
        query_family="precision_condition_adc_filtered",
        retain_any_terms=("adc", "antibody-drug", "conjugate", "folate", "fr alpha", "frα", "trop2", "her2", "napi2b", "cdh6", "b7-h4", "b7h4"),
    ),
    ClinicalTrialSearchSpec(
        label="Ovarian ADC",
        query='ADC OR "antibody drug conjugate" OR "antibody-drug conjugate" OR "folate receptor" OR "FR alpha" OR "FRα" OR TROP2 OR HER2 OR NaPi2b OR CDH6 OR "B7-H4" OR B7H4',
        strategic_lane="Ovarian ADC category momentum",
        priority=2,
        query_area="intr",
        max_pages=2,
        query_family="precision_intervention_ovarian_filtered",
        retain_any_terms=("ovarian", "fallopian", "peritoneal", "adc", "antibody-drug", "folate", "fr alpha", "frα", "trop2", "her2", "napi2b", "cdh6", "b7-h4", "b7h4"),
    ),

    # Side channels stay bounded and clearly secondary. They should never expand
    # the sponsor-evidence budget used for the oncology precision battlefield.
    ClinicalTrialSearchSpec(
        label="Alzheimer's Side Channel",
        query='Alzheimer AND (antibody OR immunotherapy OR biomarker OR ApoE4)',
        strategic_lane="Side-channel scientific drift",
        priority=4,
        query_area="term",
        max_pages=1,
        query_family="side_channel_term",
        retain_any_terms=("alzheimer", "apoe4", "antibody", "immunotherapy", "biomarker"),
    ),
    ClinicalTrialSearchSpec(
        label="Bone Disease Side Channel",
        query='("bone disease" OR osteoporosis OR osteoarthritis OR "osteogenesis imperfecta") AND (antibody OR biomarker OR biologic OR Siglec-15)',
        strategic_lane="Side-channel scientific drift",
        priority=4,
        query_area="term",
        max_pages=1,
        query_family="side_channel_term",
        retain_any_terms=("bone", "osteoporosis", "osteoarthritis", "osteogenesis", "siglec", "antibody", "biomarker", "biologic"),
    ),
)

# Precision-first but bounded for Streamlit Cloud safety.
CLINICAL_TRIALS_PAGE_SIZE = 50
CLINICAL_TRIALS_MAX_PAGES_PER_SPEC = 4
CLINICAL_TRIALS_TIMEOUT_SECONDS = 10
