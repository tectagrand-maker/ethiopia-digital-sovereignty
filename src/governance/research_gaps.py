"""Step 9: Research Gap Prioritization & Evidence Expansion Framework.

Builds a reproducible research-gap framework on top of the existing evidence,
comparative (Step 7) and case-study (Step 8) architecture. It identifies which
gaps should be researched next, why they matter, what evidence is missing, and
what type of source would appropriately address each gap.

Research-integrity rules (preserved from the project's evidence policy):

- No evidence is fabricated. Gaps are *derived* from the committed database.
- ``missing_evidence`` is a statement about the corpus, never a negative
  finding. Absence of evidence is not evidence of absence.
- The output describes **what should be researched**, not research that has
  already been completed.
- ``priority_score`` is a documented, rule-based research-planning heuristic.
  It is NOT a governance score, a country ranking, or an assessment of a
  jurisdiction.

Distinct gap scopes (spec requirement 9):

- ``ethiopia_specific``    -- per-cell gaps whose affected case is Ethiopia
- ``comparator_specific``  -- per-cell gaps whose affected case is a comparator
- ``cross_case``           -- the same dimension is empty in every case
- ``comparative_coverage`` -- a coverage imbalance between the primary case and
                              a comparator
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.evidence.models import (
    Source, Evidence, SourceType, GOVERNANCE_DIMENSIONS,
)
from src.evidence.ingestion import EvidenceSchema
from src.governance.matrix import (
    DOMAIN_TO_DIMENSION, PARTIAL_STATUS, MISSING_STATUS,
)
from src.governance.comparison import (
    available_cases, case_dimension_view, _cell_evidence_rows, CONFLICTING_STATUS,
)

PLAN_TYPE = "research_gap_plan"
SCHEMA_VERSION = 1

PRIMARY_CASE = "Ethiopia"
CROSS_CASE_LABEL = "Cross-case"

# Controlled vocabulary. Only categories supported by the repository's data
# model are implemented (spec requirement 2: no categories for appearance).
CATEGORIES = {
    "evidence_coverage",        # evidence_count == 0 for the cell
    "source_diversity",         # evidence rests on a single source
    "source_quality",           # provenance/quality deficiencies in cell evidence
    "temporal_coverage",        # evidence lacks an independently verified date
    "confidence_limitation",    # linked observations carry confidence <= 2
    "methodological_limitation",# normative-only corpus / evidence without synthesis
    "conflicting_evidence",     # recorded contradicts relation inside the cell
    "comparative_coverage",     # cross-case coverage imbalance (Step 7)
}

SCOPES = {
    "ethiopia_specific",
    "comparator_specific",
    "cross_case",
    "comparative_coverage",
}

PRIORITY_LEVELS = ("high", "medium", "low")
# score >= 7 -> high; score >= 5 -> medium; otherwise low (documented rule).
PRIORITY_THRESHOLDS = {"high": 7, "medium": 5}
MAX_PRIORITY_SCORE = 9  # importance(1-3) + severity(1-3) + breadth(0-3)

# Research-focus importance of each dimension. This is a documented research
# planning weight (see docs/research-gap-framework.md), NOT a governance score
# and NOT a claim about the dimension's real-world importance.
DIMENSION_IMPORTANCE = {
    "data_governance": 3,
    "digital_identity": 3,
    "consent_individual_agency": 3,
    "data_localization": 3,
    "citizen_rights_redress": 3,
    "institutional_accountability": 2,
    "state_capacity": 2,
    "legal_regulatory_safeguards": 2,
    "security_resilience": 2,
    "transparency": 1,
    "interoperability": 1,
    "private_sector_dependence": 1,
}

# Severity of evidence insufficiency per gap category (documented rule).
SEVERITY_WEIGHTS = {
    "evidence_coverage": 3,        # no evidence at all for the cell
    "conflicting_evidence": 3,     # recorded contradiction blocks interpretation
    "source_diversity": 2,         # single source only
    "comparative_coverage": 2,     # imbalance blocks cross-case comparison
    "confidence_limitation": 1,
    "source_quality": 1,
    "temporal_coverage": 1,
    "methodological_limitation": 1,
}

# Evidence-basis split used by the methodological_limitation rule.
NORMATIVE_BASES = {"normative", "institutional"}
EMPIRICAL_BASES = {"empirical", "implementation", "observational", "technical"}

# Documented mapping: gap category -> recommended source types. Values are the
# controlled SourceType vocabulary from src/evidence/models.py. The mapping is
# planning guidance only and does not claim any type is authoritative for every
# dimension (spec requirement 5).
RECOMMENDED_SOURCE_TYPES = {
    "evidence_coverage": ["law", "regulation", "policy", "government_document",
                          "official_webpage"],
    "source_diversity": ["institutional_report", "civil_society_report",
                         "journalism", "academic_paper", "technical_report"],
    "source_quality": ["official_webpage", "institutional_report",
                       "government_document"],
    "temporal_coverage": ["official_webpage", "institutional_report",
                          "journalism", "dataset"],
    "confidence_limitation": ["technical_report", "institutional_report",
                              "dataset", "civil_society_report"],
    "methodological_limitation": ["technical_report", "institutional_report",
                                  "dataset", "civil_society_report"],
    "conflicting_evidence": ["court_decision", "academic_paper",
                             "government_document"],
    "comparative_coverage": ["law", "regulation", "policy",
                             "institutional_report"],
}

CATEGORY_MISSING = {
    "evidence_coverage": "No real evidence records for this dimension in the "
                         "current corpus.",
    "source_diversity": "An independent second source for this dimension is not "
                        "recorded; the current evidence is single-source.",
    "source_quality": "Verified, high-provenance evidence for this dimension is "
                      "not recorded; the current records carry provenance "
                      "deficiencies.",
    "temporal_coverage": "Dated, independently verifiable evidence for this "
                         "dimension is not recorded; currency cannot be "
                         "confirmed from the records themselves.",
    "confidence_limitation": "Higher-confidence or independently verifiable "
                             "evidence for the existing interpretation is not "
                             "recorded.",
    "methodological_limitation": "Implementation, empirical or observational "
                                 "evidence for this dimension is not recorded; "
                                 "the corpus holds legal/institutional text only.",
    "conflicting_evidence": "Authoritative evidence that would resolve the "
                            "recorded contradiction is not recorded.",
    "comparative_coverage": "Evidence on the missing side of the comparison is "
                            "not recorded in the corpus.",
}

RESEARCH_QUESTION_TEMPLATES = {
    "evidence_coverage": (
        "What documented evidence exists on '{dimension}' for {jurisdiction}, "
        "and which authoritative source types (e.g. {sources}) could provide it?"
    ),
    "source_diversity": (
        "Which independent second source could corroborate or refine the "
        "single-source evidence currently recorded on '{dimension}' for "
        "{jurisdiction}?"
    ),
    "source_quality": (
        "Which verified, authoritative source could replace or strengthen the "
        "low-provenance evidence currently recorded on '{dimension}' for "
        "{jurisdiction}?"
    ),
    "temporal_coverage": (
        "Which recent or independently dated source would establish the current "
        "state of '{dimension}' for {jurisdiction}?"
    ),
    "confidence_limitation": (
        "Which higher-confidence, independently verifiable evidence could "
        "strengthen the interpretation of '{dimension}' for {jurisdiction}?"
    ),
    "methodological_limitation": (
        "Which implementation or evaluative evidence would allow '{dimension}' "
        "for {jurisdiction} to be assessed beyond the legal text already "
        "recorded?"
    ),
    "conflicting_evidence": (
        "Which authoritative source could resolve or contextualize the recorded "
        "contradiction in evidence on '{dimension}' for {jurisdiction}?"
    ),
    "comparative_coverage": (
        "Which evidence would make '{dimension}' for {jurisdiction} comparable "
        "with the other cases in the Step 7 comparative baseline?"
    ),
}

EXPECTED_VALUE_TEMPLATES = {
    "evidence_coverage": (
        "Would move '{dimension}' for {jurisdiction} from missing_evidence "
        "toward at least partial, enabling a first evidence-based interpretation "
        "and case-study coverage."
    ),
    "source_diversity": (
        "An independent second source could move '{dimension}' for "
        "{jurisdiction} from partial to supported and reduce single-source bias."
    ),
    "source_quality": (
        "Would raise the reliability of the evidence base for '{dimension}' and "
        "strengthen provenance consistency."
    ),
    "temporal_coverage": (
        "Would allow the currency of the legal/empirical state of '{dimension}' "
        "to be assessed against a verified date."
    ),
    "confidence_limitation": (
        "Would raise confidence in the interpretation of '{dimension}' or "
        "reveal where it needs revision."
    ),
    "methodological_limitation": (
        "Would add implementation/empirical evidence so '{dimension}' can be "
        "assessed beyond the law-on-paper record."
    ),
    "conflicting_evidence": (
        "Could resolve or re-frame the recorded contradiction on '{dimension}', "
        "unblocking interpretation."
    ),
    "comparative_coverage": (
        "Would enable an evidence-based pairwise reading of '{dimension}' in the "
        "Step 7 comparative baseline."
    ),
}

DEPENDENCY_TEMPLATES = {
    "evidence_coverage": [
        "None directly; follows the standard source -> acquire -> verify -> "
        "extract -> ingest pipeline.",
    ],
    "source_diversity": [
        "Requires identifying a second independent source for the dimension; "
        "existing evidence records are unchanged.",
    ],
    "source_quality": [
        "Requires acquiring/verifying the replacement source before ingest.",
    ],
    "temporal_coverage": [
        "Requires a source with an independently verifiable publication date.",
    ],
    "confidence_limitation": [
        "Requires higher-confidence or independently verifiable records; "
        "depends on source availability.",
    ],
    "methodological_limitation": [
        "Requires implementation/empirical or evaluative sources, which are "
        "typically slower to produce than statute text.",
    ],
    "conflicting_evidence": [
        "Requires an adjudicative/authoritative source; the contradiction stays "
        "recorded until then (never silently resolved).",
    ],
    "comparative_coverage": [
        "Comparator evidence acquisition is independent and parallel; the "
        "comparative report updates automatically on rebuild.",
    ],
}

LIMITATIONS = [
    "Gaps are derived only from the committed evidence database; sources that "
    "have not been acquired or extracted cannot produce evidence and therefore "
    "cannot generate per-cell evidence.",
    "priority_score reflects the project's documented research focus and the "
    "current corpus state; it is not a governance score, a country ranking, or "
    "an assessment of real-world importance.",
    "missing_evidence is a corpus statement and is never a negative finding.",
    "Recommended source types are planning guidance; no single source type is "
    "claimed authoritative for every dimension.",
    "Research questions are prompts for future work, not findings.",
    "Comparative and cross-case gaps depend on which cases are present in the "
    "corpus (available_cases()).",
]


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

def _valid_jurisdictions():
    return set(available_cases()) | {CROSS_CASE_LABEL}


class Gap(BaseModel):
    gap_id: str
    category: str
    jurisdiction: str
    affected_cases: List[str] = []
    dimension: str
    scope: str
    jurisdiction_group: str = ""
    evidence_status: str
    confidence: Optional[int] = None
    reason: str
    evidence_available: List[int] = []
    evidence_missing: str
    comparator_context: Optional[Dict] = None
    priority_score: int
    priority_level: str
    priority_factors: List[dict] = []
    priority_rationale: str = ""

    @field_validator('category')
    @classmethod
    def _check_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError(f"Invalid gap category: {v!r}")
        return v

    @field_validator('scope')
    @classmethod
    def _check_scope(cls, v):
        if v not in SCOPES:
            raise ValueError(f"Invalid gap scope: {v!r}")
        return v

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @field_validator('priority_level')
    @classmethod
    def _check_priority_level(cls, v):
        if v not in PRIORITY_LEVELS:
            raise ValueError(f"Invalid priority level: {v!r}")
        return v

    @field_validator('priority_score')
    @classmethod
    def _check_priority_score(cls, v):
        if not (1 <= v <= MAX_PRIORITY_SCORE):
            raise ValueError(f"priority_score {v} outside documented range 1-{MAX_PRIORITY_SCORE}")
        return v

    @field_validator('gap_id')
    @classmethod
    def _check_gap_id(cls, v):
        if not v or not v.strip():
            raise ValueError("gap_id must not be empty")
        return v


class ResearchAction(BaseModel):
    gap_id: str
    jurisdiction: str
    dimension: str
    category: str
    scope: str
    priority_level: str
    reason: str
    evidence_available: List[int] = []
    evidence_missing: str
    recommended_source_types: List[str] = []
    recommended_catalog_sources: List[int] = []
    research_question: str
    expected_analytical_value: str
    dependencies: List[str] = []
    provenance_requirements: List[str] = []

    @field_validator('research_question')
    @classmethod
    def _must_be_question(cls, v):
        if not v.endswith("?"):
            raise ValueError("research_question must be phrased as a question")
        return v

    @field_validator('recommended_source_types')
    @classmethod
    def _check_source_types(cls, v):
        valid = {e.value for e in SourceType}
        for t in v:
            if t not in valid:
                raise ValueError(f"Invalid source type: {t!r}")
        return v


class ResearchPlan(BaseModel):
    report_type: str = PLAN_TYPE
    schema_version: int = SCHEMA_VERSION
    note: str
    methodology: Dict
    gaps: List[Gap] = []
    prioritized_actions: List[ResearchAction] = []
    affected_dimensions: List[str] = []
    affected_cases: List[str] = []
    evidence_coverage: List[dict] = []
    research_questions: List[str] = []
    recommended_source_types: Dict[str, List[str]] = {}
    limitations: List[str] = []


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _case_scope(case):
    return "ethiopia_specific" if case == PRIMARY_CASE else "comparator_specific"


def _case_group(case):
    groups = sorted({
        e.source.jurisdiction_group
        for e in Evidence.select()
        if e.data_status == 'real'
        and e.country_or_jurisdiction == case
        and e.source.jurisdiction_group
    })
    return groups[0] if groups else ""


def _gap_id(jurisdiction, dimension, category):
    return f"{jurisdiction.upper().replace(' ', '_')}-{dimension}-{category}"


def _priority_level(score):
    if score >= PRIORITY_THRESHOLDS["high"]:
        return "high"
    if score >= PRIORITY_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _gap_sort_key(gap):
    return (-gap["priority_score"], gap["gap_id"])


def _views_for(cases):
    return {(c, d): case_dimension_view(c, d)
            for c in sorted(cases) for d in GOVERNANCE_DIMENSIONS}


def _quality_issues(rows):
    issues = []
    for e in rows:
        if not (e.locator_type and e.locator_value):
            issues.append(f"evidence {e.evidence_id}: missing locator")
        if not e.evidence_basis:
            issues.append(f"evidence {e.evidence_id}: missing evidence_basis")
        if (e.evidence_strength or 0) <= 2:
            issues.append(f"evidence {e.evidence_id}: low evidence_strength ({e.evidence_strength})")
        if (e.reliability_level or 0) <= 2:
            issues.append(f"evidence {e.evidence_id}: low reliability_level ({e.reliability_level})")
        if e.source and e.source.status == 'discovered':
            issues.append(f"evidence {e.evidence_id}: source {e.source.source_id} not yet accessed")
    return issues


def _methodological_triggers(rows, view):
    if not rows:
        return ""
    parts = []
    if view["observation_count"] == 0:
        parts.append("evidence exists but no governance observation synthesizes it")
    bases = {e.evidence_basis for e in rows if e.evidence_basis}
    if bases and bases <= NORMATIVE_BASES:
        parts.append(
            "all recorded evidence is normative/institutional (statute text); "
            "no implementation, empirical or observational evidence is recorded")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Discovery: per-cell and comparative passes
# ---------------------------------------------------------------------------

def _prioritize(case, dimension, category, view, cases, views):
    """Transparent, rule-based priority. Returns score/level/factors/rationale.

    score = dimension_importance + severity + breadth, where
      importance: DIMENSION_IMPORTANCE[dimension]
      severity:   SEVERITY_WEIGHTS[category]
      breadth:    +1 primary-case gap,
                  +1 at least one other case holds evidence for the dimension
                     (comparative importance),
                  +1 the cell is currently partial/conflicting so new evidence
                     could materially change the interpretation
    Documented in docs/research-gap-framework.md and never a governance score.
    """
    factors = []

    importance = DIMENSION_IMPORTANCE.get(dimension, 1)
    factors.append({
        "factor": "dimension_importance",
        "points": importance,
        "rationale": (f"'{dimension}' carries research-focus importance "
                      f"{importance} (documented weight, not a governance score)."),
    })

    severity = SEVERITY_WEIGHTS[category]
    factors.append({
        "factor": "severity",
        "points": severity,
        "rationale": f"category '{category}' carries severity weight {severity}.",
    })

    breadth = 0
    if case == PRIMARY_CASE:
        breadth += 1
        factors.append({
            "factor": "primary_case",
            "points": 1,
            "rationale": "Affects the primary case (Ethiopia), central to the research program.",
        })

    others = [c for c in cases if c != case and views[(c, dimension)]["evidence_count"] > 0]
    if others:
        breadth += 1
        factors.append({
            "factor": "comparative_importance",
            "points": 1,
            "rationale": (f"{len(others)} other case(s) hold evidence on "
                          f"'{dimension}'; new evidence would enable or refresh "
                          "a pairwise comparison."),
        })

    if view["evidence_status"] in (PARTIAL_STATUS, CONFLICTING_STATUS):
        breadth += 1
        factors.append({
            "factor": "interpretation_change",
            "points": 1,
            "rationale": ("Cell is currently 'partial' or 'conflicting'; new "
                          "evidence could materially change the interpretation."),
        })

    score = importance + severity + breadth
    level = _priority_level(score)
    rationale = ("; ".join(f["rationale"] for f in factors)
                 + f" -> score {score} = {level} (thresholds: "
                 + "high>=7, medium>=5, else low).")
    return {
        "priority_score": score,
        "priority_level": level,
        "priority_factors": factors,
        "priority_rationale": rationale,
    }


def _base_gap(case, dimension, category, view, rows, cases, views, reason,
              evidence_missing, scope=None):
    jurisdiction_group = _case_group(case)
    prio = _prioritize(case, dimension, category, view, cases, views)
    return {
        "gap_id": _gap_id(case, dimension, category),
        "category": category,
        "jurisdiction": case,
        "affected_cases": [case],
        "dimension": dimension,
        "scope": scope or _case_scope(case),
        "jurisdiction_group": jurisdiction_group,
        "evidence_status": view["evidence_status"],
        "confidence": view["confidence"],
        "reason": reason,
        "evidence_available": sorted({t["evidence_id"] for t in view["evidence"]}),
        "evidence_missing": evidence_missing,
        "comparator_context": None,
        **prio,
    }


def _cell_gaps(case, dimension, views, cases):
    view = views[(case, dimension)]
    rows = _cell_evidence_rows(case, dimension)
    gaps = []
    cell_missing = view["gaps"] or CATEGORY_MISSING["evidence_coverage"]

    # 1. evidence_coverage
    if view["evidence_count"] == 0:
        gaps.append(_base_gap(
            case, dimension, "evidence_coverage", view, rows, cases, views,
            reason="No real evidence records for this dimension in the current corpus.",
            evidence_missing=CATEGORY_MISSING["evidence_coverage"],
        ))
        return gaps  # an empty cell has no further cell-level deficiencies

    # 2. source_diversity
    if view["evidence_status"] != CONFLICTING_STATUS and view["source_count"] == 1:
        gaps.append(_base_gap(
            case, dimension, "source_diversity", view, rows, cases, views,
            reason=("Evidence for this dimension rests on a single source; a "
                    "second independent source would reduce single-source bias."),
            evidence_missing=CATEGORY_MISSING["source_diversity"],
        ))

    # 3. source_quality
    issues = _quality_issues(rows)
    if issues:
        gaps.append(_base_gap(
            case, dimension, "source_quality", view, rows, cases, views,
            reason="Provenance/quality deficiencies in the cell's evidence: "
                   + "; ".join(issues) + ".",
            evidence_missing=CATEGORY_MISSING["source_quality"],
        ))

    # 4. temporal_coverage
    undated = sorted(e.evidence_id for e in rows if not e.publication_date)
    if undated:
        gaps.append(_base_gap(
            case, dimension, "temporal_coverage", view, rows, cases, views,
            reason=("Evidence record(s) without an independently verified "
                    f"publication date: {', '.join('ev' + str(i) for i in undated)}. "
                    "Currency of the recorded state cannot be confirmed."),
            evidence_missing=CATEGORY_MISSING["temporal_coverage"],
        ))

    # 5. confidence_limitation
    if view["observation_count"] and view["confidence"] is not None \
            and view["confidence"] <= 2:
        gaps.append(_base_gap(
            case, dimension, "confidence_limitation", view, rows, cases, views,
            reason=("Linked governance observations carry average confidence "
                    f"{view['confidence']} (<= 2 on the 1-5 scale)."),
            evidence_missing=CATEGORY_MISSING["confidence_limitation"],
        ))

    # 6. methodological_limitation
    trigger = _methodological_triggers(rows, view)
    if trigger:
        gaps.append(_base_gap(
            case, dimension, "methodological_limitation", view, rows, cases, views,
            reason=f"Methodological limitation: {trigger}.",
            evidence_missing=CATEGORY_MISSING["methodological_limitation"],
        ))

    # 7. conflicting_evidence
    if view["conflicts"]:
        pairs = "; ".join(f"ev{c['evidence_a']} vs ev{c['evidence_b']}"
                          for c in view["conflicts"])
        gaps.append(_base_gap(
            case, dimension, "conflicting_evidence", view, rows, cases, views,
            reason=f"Recorded contradictions among linked evidence: {pairs}.",
            evidence_missing=CATEGORY_MISSING["conflicting_evidence"],
        ))

    return gaps


def _comparative_gaps(cases, views):
    if PRIMARY_CASE not in cases:
        return []
    others = [c for c in cases if c != PRIMARY_CASE]
    gaps = []

    for dimension in GOVERNANCE_DIMENSIONS:
        p_view = views[(PRIMARY_CASE, dimension)]
        p_has = p_view["evidence_count"] > 0
        other_has = {c: views[(c, dimension)]["evidence_count"] > 0 for c in others}

        for c in others:
            c_view = views[(c, dimension)]
            if p_has and not other_has[c]:
                # comparator lacks evidence the primary case holds
                prio = _prioritize(c, dimension, "comparative_coverage",
                                   c_view, cases, views)
                gaps.append({
                    "gap_id": _gap_id(c, dimension, "comparative_coverage"),
                    "category": "comparative_coverage",
                    "jurisdiction": c,
                    "affected_cases": [c],
                    "dimension": dimension,
                    "scope": "comparative_coverage",
                    "jurisdiction_group": _case_group(c),
                    "evidence_status": c_view["evidence_status"],
                    "confidence": c_view["confidence"],
                    "reason": (f"Coverage imbalance: {PRIMARY_CASE} holds "
                               f"{p_view['evidence_count']} evidence record(s) on "
                               f"'{dimension}' while {c} holds "
                               f"{c_view['evidence_count']}; cross-case comparison "
                               "is limited to one side."),
                    "evidence_available": sorted({t["evidence_id"] for t in c_view["evidence"]}),
                    "evidence_missing": CATEGORY_MISSING["comparative_coverage"],
                    "comparator_context": {
                        "primary_case": PRIMARY_CASE,
                        "primary_status": p_view["evidence_status"],
                        "comparator": c,
                        "comparator_status": c_view["evidence_status"],
                    },
                    **prio,
                })
            elif not p_has and other_has[c]:
                # primary case lacks evidence the comparator holds
                prio = _prioritize(PRIMARY_CASE, dimension, "comparative_coverage",
                                   p_view, cases, views)
                gaps.append({
                    "gap_id": _gap_id(PRIMARY_CASE, dimension, "comparative_coverage"),
                    "category": "comparative_coverage",
                    "jurisdiction": PRIMARY_CASE,
                    "affected_cases": [PRIMARY_CASE],
                    "dimension": dimension,
                    "scope": "comparative_coverage",
                    "jurisdiction_group": _case_group(PRIMARY_CASE),
                    "evidence_status": p_view["evidence_status"],
                    "confidence": p_view["confidence"],
                    "reason": (f"Coverage imbalance: {c} holds "
                               f"{c_view['evidence_count']} evidence record(s) on "
                               f"'{dimension}' while {PRIMARY_CASE} holds none; "
                               "the primary case cannot yet be compared on this "
                               "dimension."),
                    "evidence_available": [],
                    "evidence_missing": CATEGORY_MISSING["comparative_coverage"],
                    "comparator_context": {
                        "primary_case": PRIMARY_CASE,
                        "primary_status": p_view["evidence_status"],
                        "comparator": c,
                        "comparator_status": c_view["evidence_status"],
                    },
                    **prio,
                })

        if not p_has and all(not h for h in other_has.values()):
            prio = _prioritize(CROSS_CASE_LABEL, dimension, "comparative_coverage",
                               p_view, cases, views)
            gaps.append({
                "gap_id": _gap_id(CROSS_CASE_LABEL, dimension, "comparative_coverage"),
                "category": "comparative_coverage",
                "jurisdiction": CROSS_CASE_LABEL,
                "affected_cases": sorted(cases),
                "dimension": dimension,
                "scope": "cross_case",
                "jurisdiction_group": "",
                "evidence_status": p_view["evidence_status"],
                "confidence": p_view["confidence"],
                "reason": ("No case in the corpus holds evidence for "
                           f"'{dimension}'; the gap is shared across all cases."),
                "evidence_available": [],
                "evidence_missing": CATEGORY_MISSING["evidence_coverage"],
                "comparator_context": {
                    "primary_case": PRIMARY_CASE,
                    "primary_status": p_view["evidence_status"],
                    "comparators": others,
                    "comparator_statuses": {c: views[(c, dimension)]["evidence_status"] for c in others},
                },
                **prio,
            })

    return gaps


def discover_gaps(cases=None, dimension=None):
    """Deterministic gap inventory derived from the committed evidence database."""
    if cases is None:
        cases = available_cases()
    cases = sorted(set(cases))
    views = _views_for(cases)

    gaps = []
    for c in cases:
        for d in GOVERNANCE_DIMENSIONS:
            gaps.extend(_cell_gaps(c, d, views, cases))
    gaps.extend(_comparative_gaps(cases, views))

    if dimension is not None:
        gaps = [g for g in gaps if g["dimension"] == dimension]

    gaps.sort(key=_gap_sort_key)
    return gaps


# ---------------------------------------------------------------------------
# Evidence expansion interface (spec requirement 6)
# ---------------------------------------------------------------------------

def evidence_expansion_requirements():
    """Checklist for adding newly verified evidence without bypassing the
    existing ingestion/provenance system."""
    return {
        "note": ("New evidence must flow through the existing ingestion and "
                 "provenance pipeline. Never insert unverified research material "
                 "directly into the evidence database."),
        "required_record_fields": [
            "title", "source_type", "publisher_or_author",
            "country_or_jurisdiction", "domain_theme", "claim",
            "evidence_summary", "reliability_level", "evidence_strength",
        ],
        "recommended_record_fields": [
            "evidence_basis", "locator_type", "locator_value", "citation",
            "source_url", "publication_date", "source_excerpt",
            "interpretation", "data_status",
        ],
        "provenance_steps": [
            "1. Register the source: `python -m src.cli source add ...` (or extend data/sources/catalog.json).",
            "2. Acquire the raw source: `python -m src.cli source acquire --id <id>` (records SHA-256 provenance).",
            "3. Verify integrity: `python -m src.cli source verify --id <id>`.",
            "4. Extract text: `python -m src.cli extract --file <raw_path> --source-id <id>`.",
            "5. Ingest evidence records: `python -m src.cli ingest --type json --file <corpus_file> --source-id <id>`.",
            "6. Link governance observations to the new evidence ids where a dimension assessment is expected.",
        ],
        "ingest_route": ("src.evidence.ingestion.ingest_evidence / import_from_json "
                         "/ import_from_csv"),
        "source_id_required": ("The evidence database never accepts unlinked "
                               "records; a registered source_id is required at ingest time."),
    }


def validate_evidence_record(record):
    """Pre-ingestion validation of a prospective evidence record.

    Does NOT insert anything. Checks the required fields and reuses the
    existing EvidenceSchema for field-level validation.
    """
    required = evidence_expansion_requirements()["required_record_fields"]
    missing = [f for f in required
               if not record.get(f) or str(record.get(f)).strip() == ""]
    errors = []
    try:
        EvidenceSchema(**record)
    except ValidationError as e:
        errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
    return {
        "valid": not missing and not errors,
        "missing_required": missing,
        "validation_errors": errors,
    }


# ---------------------------------------------------------------------------
# Research actions (spec requirements 4-5)
# ---------------------------------------------------------------------------

def _catalog_sources_for_dimension(dimension):
    """Source ids in the catalog (status 'discovered', not yet acquired) whose
    research domains map onto the given governance dimension."""
    out = []
    for s in Source.select().where(
            (Source.data_status == 'real') & (Source.status == 'discovered')):
        domains = [d.strip() for d in (s.research_domains or '').split(',')
                   if d.strip()]
        mapped = {DOMAIN_TO_DIMENSION.get(d) for d in domains}
        if dimension in mapped:
            out.append(s.source_id)
    return sorted(out)


def _research_action(gap):
    sources = sorted(RECOMMENDED_SOURCE_TYPES.get(gap["category"],
                                                  ["institutional_report"]))
    q = RESEARCH_QUESTION_TEMPLATES[gap["category"]].format(
        jurisdiction=gap["jurisdiction"], dimension=gap["dimension"],
        sources=", ".join(sources))
    value = EXPECTED_VALUE_TEMPLATES[gap["category"]].format(
        jurisdiction=gap["jurisdiction"], dimension=gap["dimension"])
    return {
        "gap_id": gap["gap_id"],
        "jurisdiction": gap["jurisdiction"],
        "dimension": gap["dimension"],
        "category": gap["category"],
        "scope": gap["scope"],
        "priority_level": gap["priority_level"],
        "reason": gap["reason"],
        "evidence_available": list(gap["evidence_available"]),
        "evidence_missing": gap["evidence_missing"],
        "recommended_source_types": sources,
        "recommended_catalog_sources": _catalog_sources_for_dimension(gap["dimension"]),
        "research_question": q,
        "expected_analytical_value": value,
        "dependencies": list(DEPENDENCY_TEMPLATES[gap["category"]]),
        "provenance_requirements": list(evidence_expansion_requirements()["provenance_steps"]),
    }


# ---------------------------------------------------------------------------
# Research plan assembly
# ---------------------------------------------------------------------------

def _methodology_block():
    return {
        "priority_formula": (
            "score = dimension_importance + severity + breadth; "
            "high >= 7, medium >= 5, else low (max 9)."
        ),
        "breadth_factors": [
            "primary_case (+1): gap affects the primary case (Ethiopia)",
            "comparative_importance (+1): another case holds evidence on the dimension",
            "interpretation_change (+1): cell is currently partial or conflicting",
        ],
        "dimension_importance": dict(sorted(DIMENSION_IMPORTANCE.items())),
        "severity_weights": dict(sorted(SEVERITY_WEIGHTS.items())),
        "priority_thresholds": PRIORITY_THRESHOLDS,
        "disclaimer": (
            "These are documented research-planning weights, not governance "
            "scores, country rankings, or assessments of real-world importance."
        ),
        "categories": sorted(CATEGORIES),
        "scopes": sorted(SCOPES),
    }


def _coverage_rows(gaps, cases):
    rows = []
    cases = sorted(cases)
    dims = sorted({g["dimension"] for g in gaps})
    for c in cases:
        for d in dims:
            view = case_dimension_view(c, d)
            rows.append({
                "case": c,
                "dimension": d,
                "evidence_status": view["evidence_status"],
                "evidence_count": view["evidence_count"],
                "source_count": view["source_count"],
                "observation_count": view["observation_count"],
                "confidence": view["confidence"],
            })
    rows.sort(key=lambda r: (r["case"], r["dimension"]))
    return rows


def research_plan(case=None, dimension=None, min_priority=None):
    """Deterministic, machine-readable research plan.

    ``case`` filters gaps to a jurisdiction; ``dimension`` filters to one of the
    12 dimensions; ``min_priority`` filters to at least the given priority level.
    """
    gaps = discover_gaps(dimension=dimension)
    if case is not None:
        gaps = [g for g in gaps
                if g["jurisdiction"] == case or case in g["affected_cases"]]
    if min_priority is not None:
        if min_priority not in PRIORITY_LEVELS:
            raise ValueError(f"min_priority must be one of {list(PRIORITY_LEVELS)}")
        rank = {l: i for i, l in enumerate(PRIORITY_LEVELS)}
        gaps = [g for g in gaps
                if rank[g["priority_level"]] <= rank[min_priority]]

    gaps.sort(key=_gap_sort_key)
    actions = [_research_action(g) for g in gaps]

    affected_dimensions = sorted({g["dimension"] for g in gaps})
    affected_cases = sorted(
        ({g["jurisdiction"] for g in gaps}
         | {c for g in gaps for c in g["affected_cases"]})
        - {CROSS_CASE_LABEL}
    )
    coverage = _coverage_rows(gaps, affected_cases)

    return {
        "report_type": PLAN_TYPE,
        "schema_version": SCHEMA_VERSION,
        "note": (
            "Research gap prioritization plan. Gaps are derived from the "
            "committed evidence database; missing evidence is never a negative "
            "finding; priorities are research-planning heuristics, not "
            "governance scores or country rankings."
        ),
        "methodology": _methodology_block(),
        "gaps": gaps,
        "prioritized_actions": actions,
        "affected_dimensions": affected_dimensions,
        "affected_cases": affected_cases,
        "evidence_coverage": coverage,
        "research_questions": [a["research_question"] for a in actions],
        "recommended_source_types": {
            k: sorted(v) for k, v in sorted(RECOMMENDED_SOURCE_TYPES.items())
        },
        "limitations": list(LIMITATIONS),
    }


# ---------------------------------------------------------------------------
# Validation (spec requirement 10)
# ---------------------------------------------------------------------------

def _validate_gap_refs(gap):
    valid_jurisdictions = _valid_jurisdictions()
    if gap["jurisdiction"] not in valid_jurisdictions:
        raise ValueError(
            f"Gap {gap['gap_id']}: invalid jurisdiction {gap['jurisdiction']!r}.")
    for c in gap["affected_cases"]:
        if c not in valid_jurisdictions:
            raise ValueError(
                f"Gap {gap['gap_id']}: invalid affected case {c!r}.")
    for eid in gap["evidence_available"]:
        e = Evidence.get_or_none(Evidence.evidence_id == eid)
        if not e:
            raise ValueError(
                f"Gap {gap['gap_id']}: orphan evidence reference {eid}.")
        if gap["jurisdiction"] in valid_jurisdictions and gap["jurisdiction"] != CROSS_CASE_LABEL \
                and e.country_or_jurisdiction != gap["jurisdiction"]:
            raise ValueError(
                f"Gap {gap['gap_id']}: evidence {eid} jurisdiction "
                f"({e.country_or_jurisdiction}) does not match gap "
                f"jurisdiction ({gap['jurisdiction']}).")


def validate_plan(plan):
    """Validate a research plan against the schema and the database.

    Raises pydantic.ValidationError on schema violations and ValueError on
    database-integrity violations. Returns the parsed model on success.
    """
    model = ResearchPlan(**plan)
    gaps = plan["gaps"]
    actions = plan["prioritized_actions"]

    ids = [g["gap_id"] for g in gaps]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate gap identifiers in the plan.")

    if len(actions) != len(gaps):
        raise ValueError("prioritized_actions must have exactly one entry per gap.")

    expected = sorted(gaps, key=_gap_sort_key)
    if [g["gap_id"] for g in gaps] != [g["gap_id"] for g in expected]:
        raise ValueError("Gaps are not in deterministic priority order.")

    for gap in gaps:
        _validate_gap_refs(gap)

    for action, gap in zip(actions, gaps):
        if action["gap_id"] != gap["gap_id"]:
            raise ValueError("Research action gap_id does not match the gap inventory.")
        if action["priority_level"] != gap["priority_level"]:
            raise ValueError("priority level mismatch between gap and action.")

    return model


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def plan_to_json(plan):
    return json.dumps(plan, indent=2, ensure_ascii=False)


def plan_to_markdown(plan):
    """Deterministic human-readable rendering for research planning."""
    lines = []
    lines.append("# Research Gap Prioritization Plan")
    lines.append("")
    lines.append(plan["note"])
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append(f"- formula: {plan['methodology']['priority_formula']}")
    lines.append(f"- disclaimer: {plan['methodology']['disclaimer']}")
    lines.append("")

    lines.append(f"## Gap inventory ({len(plan['gaps'])})")
    lines.append("")
    for gap in plan["gaps"]:
        lines.append(f"### {gap['gap_id']} — {gap['priority_level']}")
        lines.append("")
        lines.append(f"- case: `{gap['jurisdiction']}` ({gap['scope']})")
        lines.append(f"- dimension: `{gap['dimension']}` "
                     f"(status: {gap['evidence_status']})")
        lines.append(f"- category: `{gap['category']}`")
        lines.append(f"- score: {gap['priority_score']} "
                     f"({', '.join(f['factor'] for f in gap['priority_factors'])})")
        lines.append(f"- reason: {gap['reason']}")
        if gap["evidence_available"]:
            lines.append("- evidence available: "
                         + ", ".join(f"ev{i}" for i in gap["evidence_available"]))
        lines.append(f"- evidence missing: {gap['evidence_missing']}")
        lines.append("")

    lines.append(f"## Prioritized research actions ({len(plan['prioritized_actions'])})")
    lines.append("")
    for action in plan["prioritized_actions"]:
        lines.append(f"### {action['gap_id']}")
        lines.append("")
        lines.append(f"- question: {action['research_question']}")
        lines.append("- recommended source types: "
                     + ", ".join(action["recommended_source_types"]))
        if action["recommended_catalog_sources"]:
            lines.append("- catalog sources already targeting this dimension: "
                         + ", ".join(f"#{s}" for s in action["recommended_catalog_sources"]))
        lines.append(f"- expected value: {action['expected_analytical_value']}")
        lines.append(f"- dependencies: {'; '.join(action['dependencies'])}")
        lines.append("")

    lines.append("## Research questions")
    lines.append("")
    for q in plan["research_questions"]:
        lines.append(f"- {q}")
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    for limitation in plan["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 8 integration (spec requirement 8)
# ---------------------------------------------------------------------------

def gaps_for_jurisdiction(jurisdiction):
    """Compact gap references for a case-study dossier (Step 8 integration).

    Returns a list of {gap_id, category, scope, dimension, evidence_status,
    priority_level} entries. The dossier references these; it does not duplicate
    the underlying gap definitions.
    """
    gaps = discover_gaps()
    refs = []
    for gap in gaps:
        if jurisdiction == gap["jurisdiction"] or jurisdiction in gap["affected_cases"]:
            refs.append({
                "gap_id": gap["gap_id"],
                "category": gap["category"],
                "scope": gap["scope"],
                "dimension": gap["dimension"],
                "evidence_status": gap["evidence_status"],
                "priority_level": gap["priority_level"],
            })
    refs.sort(key=lambda r: r["gap_id"])
    return refs
