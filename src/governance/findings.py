"""Step 11: Evidence Re-analysis & Research Findings Synthesis.

Builds a reproducible findings layer on top of the verified evidence,
governance-observation, comparative (Step 7), case-study (Step 8) and
research-gap (Step 9) architecture. The report synthesizes what the current
corpus *establishes* and, explicitly, what it does **not** establish.

Research-integrity rules preserved from the project's evidence policy:

- ``missing_evidence`` is a statement about the corpus, never a negative
  finding (absence of evidence is not evidence of absence).
- Findings are *derived* from the committed evidence database; no facts are
  invented and no numeric governance scores, indices or rankings are produced.
- Evidence, observation, interpretation, limitation and research gap are kept
  as distinct layers: claims come from evidence records, interpretation text
  comes from governance observations and is never silently converted into
  evidence, and limitations explicitly mark where the corpus cannot support a
  conclusion.
- Co-occurrence of evidence across dimensions is reported as an evidence
  pattern, never as a causal claim.
- The report is deterministic: identical database state produces byte-identical
  JSON. No timestamps or randomized content are emitted.

The opened findings sit on top of the resolved research gaps: Step 10 closed
five gaps; this layer records that closure in ``data/evidence/resolved_gaps.json``
(validated against ``discover_gaps()``) and keeps the remaining gaps visible as
corpus-limitation findings.
"""

import hashlib
import json
import os
from collections import Counter
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from src.evidence.models import (
    Source, Evidence, EvidenceRelation, GovernanceObservation,
    GOVERNANCE_DIMENSIONS,
)
from src.governance.matrix import (
    SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS,
    _jurisdiction_evidence_ids,
)
from src.governance.comparison import (
    case_summary, available_cases, case_dimension_view, _cell_observations,
    _pairwise_note, CONFLICTING_STATUS,
)
from src.governance.research_gaps import (
    discover_gaps, PRIMARY_CASE, CROSS_CASE_LABEL, NORMATIVE_BASES,
)

REPORT_TYPE = "evidence_findings_synthesis"
SCHEMA_VERSION = 1

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RESOLVED_GAPS_PATH = os.path.join(REPO_ROOT, 'data', 'evidence', 'resolved_gaps.json')

# Controlled finding-type vocabulary (spec: no invented categories).
FINDING_TYPES = {
    "supported_finding",        # cell is supported (>=2 records, >=2 sources)
    "partial_finding",          # cell is partial (single-record/single-source basis)
    "conflicting_finding",      # recorded contradiction inside the cell
    "evidence_limitation",      # corpus coverage does not support a conclusion
    "comparative_finding",      # cross-case comparison, both sides evidenced
    "research_gap",             # a current gap surfaced as a finding (reserved)
}

STATEMENT_ORIGINS = {
    "evidence_derived",          # statement is directly derived from counts/status
    "analytical_interpretation", # statement is an explicit analytical classification
    "corpus_limitation",         # statement describes what the corpus lacks
}

# Evidence-coverage patterns used by evidence_limitation findings.
PATTERNS = {
    "insufficient_evidence",     # evidence exists on one side only / cell empty
    "not_comparable",            # neither side of the comparison holds evidence
    "contradiction",             # recorded conflicting evidence
}

# Cross-dimension patterns (spec: deterministic, non-causal).
CROSS_DIMENSION_PATTERNS = {
    "shared_source_pattern",      # one source contributes evidence to >=2 dimensions
    "recurring_evidence_limitation",  # dimensions covered only by normative text
    "no_causal_inference",        # explicit integrity boundary of the report
}

VALID_STATUSES = {
    SUPPORTED_STATUS, PARTIAL_STATUS, CONFLICTING_STATUS, MISSING_STATUS,
}


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

class EvidenceRef(BaseModel):
    """Traceable reference to one evidence record backing a finding."""
    evidence_id: int
    source_id: int
    source_title: str = ""
    claim: str
    evidence_basis: Optional[str] = None
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    citation: Optional[str] = None


class ObservationRef(BaseModel):
    """Reference to one governance observation whose assessment informs a
    finding's interpretation layer (never merged into the statement)."""
    observation_id: int
    indicator: str
    confidence: Optional[int] = None


class ResearchGapRef(BaseModel):
    """Reference to a current Step 9 research gap touching the cell."""
    gap_id: str
    category: str
    scope: str
    dimension: str
    evidence_status: str
    priority_level: str


class Finding(BaseModel):
    """One (case, dimension) synthesis finding derived from the corpus."""
    finding_id: str
    finding_type: str
    jurisdiction: str
    dimension: str
    evidence_status: str
    confidence: Optional[int] = None
    pattern: str = ""
    statement: str
    statement_origin: str
    evidence_refs: List[EvidenceRef] = []
    observation_refs: List[ObservationRef] = []
    interpretation: List[str] = []
    limitations: List[str] = []
    research_gap_refs: List[ResearchGapRef] = []

    @field_validator('finding_type')
    @classmethod
    def _check_finding_type(cls, v):
        if v not in FINDING_TYPES:
            raise ValueError(f"Invalid finding_type: {v!r}")
        return v

    @field_validator('statement_origin')
    @classmethod
    def _check_origin(cls, v):
        if v not in STATEMENT_ORIGINS:
            raise ValueError(f"Invalid statement_origin: {v!r}")
        return v

    @field_validator('evidence_status')
    @classmethod
    def _check_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid evidence_status: {v!r}")
        return v

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @field_validator('confidence')
    @classmethod
    def _check_confidence(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError(f"confidence {v} outside documented range 1-5")
        return v


class ComparisonBlock(BaseModel):
    """Explicit side-by-side evidence basis of a comparative finding."""
    ethiopia_evidence_ids: List[int] = []
    ethiopia_status: str
    ethiopia_confidence: Optional[int] = None
    comparator_evidence_ids: List[int] = []
    comparator_status: str
    comparator_confidence: Optional[int] = None
    cross_case_note: str = ""


class ComparativeFinding(BaseModel):
    """A cross-case finding. Only produced where evidence exists to compare;
    unequal/absent coverage is reported as an ``evidence_limitation`` finding."""
    finding_id: str
    finding_type: str
    jurisdiction: str
    dimension: str
    evidence_status: str
    support_relation: str = ""
    statement: str
    statement_origin: str
    pair: List[str]
    comparison: ComparisonBlock
    confidence: Optional[int] = None
    pattern: str = ""
    evidence_refs: List[EvidenceRef] = []
    observation_refs: List[ObservationRef] = []
    interpretation: List[str] = []
    limitations: List[str] = []
    research_gap_refs: List[ResearchGapRef] = []

    @field_validator('finding_type')
    @classmethod
    def _check_finding_type(cls, v):
        if v not in FINDING_TYPES:
            raise ValueError(f"Invalid finding_type: {v!r}")
        return v

    @field_validator('statement_origin')
    @classmethod
    def _check_origin(cls, v):
        if v not in STATEMENT_ORIGINS:
            raise ValueError(f"Invalid statement_origin: {v!r}")
        return v

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @model_validator(mode='after')
    def _pair_valid(self):
        if len(self.pair) != 2 or len(set(self.pair)) != 2:
            raise ValueError("Comparative findings require exactly 2 distinct cases.")
        return self


class CrossDimensionFinding(BaseModel):
    """A pattern spanning governance dimensions (never a causal claim)."""
    finding_id: str
    pattern: str
    scope: str
    statement: str
    dimensions: List[str] = []
    evidence_ids: List[int] = []
    dimension_counts: Dict[str, int] = {}

    @field_validator('pattern')
    @classmethod
    def _check_pattern(cls, v):
        if v not in CROSS_DIMENSION_PATTERNS:
            raise ValueError(f"Invalid cross-dimension pattern: {v!r}")
        return v


class CorpusState(BaseModel):
    sources: int
    evidence: int
    observations: int
    relations: int
    cases: List[str]
    corpus_digest: str


class CoverageRow(BaseModel):
    case: str
    dimension: str
    evidence_status: str
    evidence_count: int
    source_count: int
    observation_count: int
    confidence: Optional[int] = None


class DimensionSummary(BaseModel):
    dimension: str
    cases: Dict[str, dict]
    finding_ids: List[str] = []
    comparative_finding_ids: List[str] = []


class EthPrimarySynthesis(BaseModel):
    case: str = PRIMARY_CASE
    status_counts: Dict[str, int] = {}
    dimensions_with_coverage: List[str] = []
    confidence_average: Optional[int] = None
    primary_finding_ids: List[str] = []
    comparative_finding_ids: List[str] = []
    cross_dimension_finding_ids: List[str] = []
    limitations: List[str] = []


class ResolvedGapRecord(BaseModel):
    """A research gap closed by later evidence; committed and validated."""
    gap_id: str
    category: str
    jurisdiction: str
    dimension: str
    resolving_evidence_ids: List[int]
    resolution_note: str = ""


class RemainingGapRef(BaseModel):
    gap_id: str
    category: str
    scope: str
    jurisdiction: str
    dimension: str
    evidence_status: str
    priority_level: str
    priority_score: int


class FindingsReport(BaseModel):
    report_type: str = REPORT_TYPE
    schema_version: int = SCHEMA_VERSION
    note: str
    methodology: Dict
    corpus_state: CorpusState
    cases: List[dict]
    dimensions: List[DimensionSummary]
    findings: List[Finding] = []
    comparative_findings: List[ComparativeFinding] = []
    cross_dimension_findings: List[CrossDimensionFinding] = []
    ethiopia_synthesis: EthPrimarySynthesis
    evidence_coverage: List[CoverageRow] = []
    resolved_research_gaps: List[ResolvedGapRecord] = []
    remaining_research_gaps: List[RemainingGapRef] = []
    limitations: List[str] = []

    @field_validator('dimensions')
    @classmethod
    def _cover_all_dimensions(cls, v):
        ids = [d.dimension for d in v]
        if sorted(ids) != sorted(GOVERNANCE_DIMENSIONS):
            raise ValueError("Report dimensions must cover the 12 governance dimensions.")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jurlabel(jurisdiction):
    """Stable machine label used in finding_ids (mirrors the gap-id convention)."""
    if jurisdiction == CROSS_CASE_LABEL:
        return "CROSS_CASE"
    return jurisdiction.upper().replace(' ', '_')


def _trace_to_ref(trace):
    return {
        "evidence_id": trace["evidence_id"],
        "source_id": trace["source_id"],
        "source_title": trace.get("source_title") or "",
        "claim": trace.get("claim") or "",
        "evidence_basis": trace.get("evidence_basis"),
        "locator_type": trace.get("locator_type"),
        "locator_value": trace.get("locator_value"),
        "citation": trace.get("citation"),
    }


def _observation_refs(jurisdiction, dimension):
    refs = []
    for o in _cell_observations(jurisdiction, dimension):
        refs.append({
            "observation_id": o.observation_id,
            "indicator": o.indicator,
            "confidence": o.confidence,
        })
    refs.sort(key=lambda r: r["observation_id"])
    return refs


def _current_gaps_index():
    gaps = discover_gaps()
    return {g["gap_id"]: g for g in gaps}


def _gap_refs(cell_gaps):
    refs = []
    for g in cell_gaps:
        refs.append({
            "gap_id": g["gap_id"],
            "category": g["category"],
            "scope": g["scope"],
            "dimension": g["dimension"],
            "evidence_status": g["evidence_status"],
            "priority_level": g["priority_level"],
        })
    refs.sort(key=lambda r: r["gap_id"])
    return refs


def _conflicts_text(view):
    return "; ".join(
        f"ev{c['evidence_a']} vs ev{c['evidence_b']}" for c in view["conflicts"])


# ---------------------------------------------------------------------------
# Per-cell findings
# ---------------------------------------------------------------------------

def _cell_finding(jurisdiction, dimension, gap_index):
    view = case_dimension_view(jurisdiction, dimension)
    n = view["evidence_count"]
    s = view["source_count"]
    status = view["evidence_status"]

    if n == 0:
        finding_type = "evidence_limitation"
        origin = "corpus_limitation"
        pattern = "insufficient_evidence"
        statement = (
            f"No real evidence records on '{dimension}' for {jurisdiction} exist "
            "in the current corpus; there is insufficient evidence to conclude. "
            "missing_evidence is a corpus statement, never a negative assessment."
        )
        limitations = [
            "Absence of evidence is not evidence of absence; a later "
            "acquisition round may change this cell.",
        ]
    elif status == CONFLICTING_STATUS:
        finding_type = "conflicting_finding"
        origin = "evidence_derived"
        pattern = "contradiction"
        statement = (
            f"Recorded evidence on '{dimension}' for {jurisdiction} is "
            f"conflicting ({n} record(s) from {s} source(s)) and no authoritative "
            f"record in the corpus resolves the contradiction(s): {_conflicts_text(view)}."
        )
        limitations = [
            "Contradictions remain recorded and unresolved.",
        ]
    elif status == SUPPORTED_STATUS:
        finding_type = "supported_finding"
        origin = "evidence_derived"
        pattern = ""
        statement = (
            f"Supported by evidence: {n} real record(s) from {s} distinct "
            f"source(s) currently establish a documented state for '{dimension}' "
            f"in {jurisdiction}."
        )
        limitations = []
    else:
        finding_type = "partial_finding"
        origin = "evidence_derived"
        pattern = ""
        statement = (
            f"Partially evidenced: {n} real record(s) from {s} source(s) "
            f"currently establish a partial, single-source basis for '{dimension}' "
            f"in {jurisdiction}; the basis is not yet fully triangulated."
        )
        limitations = []

    if (finding_type in ("supported_finding", "partial_finding")
            and view["source_count"] == 1):
        limitations.append(
            "Single-source body of evidence; independence is not yet corroborated "
            "by a second source.")

    confidence = view["confidence"]  # rounded mean of linked observation confidence

    cell_gaps = [
        g for g in gap_index.values()
        if g["jurisdiction"] == jurisdiction and g["dimension"] == dimension
    ]

    return {
        "finding_id": f"{_jurlabel(jurisdiction)}-{dimension}-{finding_type}",
        "finding_type": finding_type,
        "jurisdiction": jurisdiction,
        "dimension": dimension,
        "evidence_status": status,
        "confidence": confidence,
        "pattern": pattern,
        "statement": statement,
        "statement_origin": origin,
        "evidence_refs": [_trace_to_ref(t) for t in view["evidence"]],
        "observation_refs": _observation_refs(jurisdiction, dimension),
        "interpretation": list(view["interpretation"]),
        "limitations": limitations,
        "research_gap_refs": _gap_refs(cell_gaps),
    }


# ---------------------------------------------------------------------------
# Comparative findings (Ethiopia-primary pairings)
# ---------------------------------------------------------------------------

def _support_relation(eth_status, comp_status):
    if CONFLICTING_STATUS in (eth_status, comp_status):
        return "conflicting"
    if eth_status == SUPPORTED_STATUS and comp_status == SUPPORTED_STATUS:
        return "both_supported"
    if eth_status == SUPPORTED_STATUS and comp_status == PARTIAL_STATUS:
        return "ethiopia_more_supported"
    if eth_status == PARTIAL_STATUS and comp_status == SUPPORTED_STATUS:
        return "comparator_more_supported"
    return "broadly_similar"


def _comparative_gap_refs(dimension, comparator, gap_index):
    relevant = [
        g for g in gap_index.values()
        if g["category"] == "comparative_coverage" and g["dimension"] == dimension
        and g["jurisdiction"] in {comparator, PRIMARY_CASE, CROSS_CASE_LABEL}
    ]
    return _gap_refs(relevant)


def _comparative_findings(cases, gap_index):
    if PRIMARY_CASE not in cases:
        return []
    comparators = sorted(c for c in cases if c != PRIMARY_CASE)
    findings = []

    for dimension in GOVERNANCE_DIMENSIONS:
        eth_view = case_dimension_view(PRIMARY_CASE, dimension)
        for comp in comparators:
            comp_view = case_dimension_view(comp, dimension)
            eth_has = eth_view["evidence_count"] > 0
            comp_has = comp_view["evidence_count"] > 0
            j1, j2 = sorted([PRIMARY_CASE, comp], key=_jurlabel)

            block = {
                "ethiopia_evidence_ids": sorted(
                    [e["evidence_id"] for e in eth_view["evidence"]]),
                "ethiopia_status": eth_view["evidence_status"],
                "ethiopia_confidence": eth_view["confidence"],
                "comparator_evidence_ids": sorted(
                    [e["evidence_id"] for e in comp_view["evidence"]]),
                "comparator_status": comp_view["evidence_status"],
                "comparator_confidence": comp_view["confidence"],
                "cross_case_note": _pairwise_note(eth_view, comp_view),
            }

            if eth_has and comp_has:
                relation = _support_relation(
                    eth_view["evidence_status"], comp_view["evidence_status"])
                messages = {
                    "both_supported": (
                        f"Both {PRIMARY_CASE} and {comp} hold supported evidence "
                        f"on '{dimension}'."),
                    "ethiopia_more_supported": (
                        f"{PRIMARY_CASE} holds supported evidence on '{dimension}' "
                        f"while {comp}'s coverage is partial."),
                    "comparator_more_supported": (
                        f"{comp} holds supported evidence on '{dimension}' while "
                        f"{PRIMARY_CASE}'s coverage is partial."),
                    "broadly_similar": (
                        f"{PRIMARY_CASE} and {comp} show broadly similar partial "
                        f"evidence coverage on '{dimension}'."),
                    "conflicting": (
                        f"Evidence on '{dimension}' conflicts on at least one side "
                        f"of the {PRIMARY_CASE} vs {comp} comparison."),
                }
                findings.append({
                    "finding_id": (
                        f"CROSS_CASE-{dimension}-comparative_finding-"
                        f"{_jurlabel(j1)}-{_jurlabel(j2)}"),
                    "finding_type": "comparative_finding",
                    "jurisdiction": CROSS_CASE_LABEL,
                    "dimension": dimension,
                    "evidence_status": (
                        f"{eth_view['evidence_status']} vs {comp_view['evidence_status']}"),
                    "support_relation": relation,
                    "statement": messages[relation],
                    "statement_origin": "analytical_interpretation",
                    "pair": [j1, j2],
                    "comparison": block,
                    "confidence": None,
                    "pattern": "",
                    "evidence_refs": (
                        [_trace_to_ref(t) for t in eth_view["evidence"]]
                        + [_trace_to_ref(t) for t in comp_view["evidence"]]),
                    "observation_refs": (
                        _observation_refs(PRIMARY_CASE, dimension)
                        + _observation_refs(comp, dimension)),
                    "interpretation": (
                        list(eth_view["interpretation"])
                        + list(comp_view["interpretation"])),
                    "limitations": [
                        "Comparative classification compares recorded evidence "
                        "coverage; it is not a score, index or ranking.",
                    ],
                    "research_gap_refs": _comparative_gap_refs(
                        dimension, comp, gap_index),
                })
            else:
                if not eth_has and not comp_has:
                    pattern = "not_comparable"
                    limitation = (
                        f"Neither {PRIMARY_CASE} nor {comp} holds evidence on "
                        f"'{dimension}'; the cells are not comparable.")
                else:
                    pattern = "insufficient_evidence"
                    limitation = (
                        f"Coverage imbalance on '{dimension}': "
                        + (f"{PRIMARY_CASE} holds evidence but {comp} holds none"
                           if eth_has else
                           f"{comp} holds evidence but {PRIMARY_CASE} holds none")
                        + "; the pairwise comparison is limited to one side.")
                refs = ([_trace_to_ref(t) for t in eth_view["evidence"]]
                        + [_trace_to_ref(t) for t in comp_view["evidence"]])
                findings.append({
                    "finding_id": (
                        f"CROSS_CASE-{dimension}-evidence_limitation-"
                        f"{_jurlabel(j1)}-{_jurlabel(j2)}"),
                    "finding_type": "evidence_limitation",
                    "jurisdiction": CROSS_CASE_LABEL,
                    "dimension": dimension,
                    "evidence_status": (
                        f"{eth_view['evidence_status']} vs {comp_view['evidence_status']}"),
                    "support_relation": "",
                    "statement": f"Comparative evidence limitation: {limitation}.",
                    "statement_origin": "corpus_limitation",
                    "pair": [j1, j2],
                    "comparison": block,
                    "confidence": None,
                    "pattern": pattern,
                    "evidence_refs": refs,
                    "observation_refs": (
                        _observation_refs(PRIMARY_CASE, dimension)
                        + _observation_refs(comp, dimension)),
                    "interpretation": (
                        list(eth_view["interpretation"])
                        + list(comp_view["interpretation"])),
                    "limitations": [
                        "Coverage imbalance limits cross-case comparison; this "
                        "is a statement about the corpus, not about either "
                        "jurisdiction.",
                    ],
                    "research_gap_refs": _comparative_gap_refs(
                        dimension, comp, gap_index),
                })
    return findings


# ---------------------------------------------------------------------------
# Cross-dimension findings
# ---------------------------------------------------------------------------

def _normative_only(view):
    bases = {t.get("evidence_basis") for t in view["evidence"] if t.get("evidence_basis")}
    return bool(bases) and bases <= NORMATIVE_BASES


def _cross_dimension_findings(cases):
    findings = []

    # shared_source_pattern: one source contributes evidence to >=2 dimensions.
    for case in sorted(cases):
        source_dims = {}
        for dim in GOVERNANCE_DIMENSIONS:
            view = case_dimension_view(case, dim)
            for _t in view["evidence"]:
                source_dims.setdefault(_t["source_id"], {}).setdefault(
                    "dims", set()).add(dim)
                source_dims[_t["source_id"]].setdefault(
                    "evidence", set()).add(_t["evidence_id"])
        for sid in sorted(source_dims):
            dims = sorted(source_dims[sid]["dims"])
            if len(dims) < 2:
                continue
            findings.append({
                "finding_id": f"CROSS_DIMENSION-shared_source_pattern-"
                              f"{_jurlabel(case)}-src{sid}",
                "pattern": "shared_source_pattern",
                "scope": case,
                "statement": (
                    f"Source {sid} contributes evidence to {len(dims)} governance "
                    f"dimensions for {case}: {', '.join(dims)}. This records an "
                    "evidence-distribution pattern, not a causal link."),
                "dimensions": dims,
                "evidence_ids": sorted(source_dims[sid]["evidence"]),
                "dimension_counts": {d: 1 for d in dims},
            })

    # recurring_evidence_limitation: primary-case dimensions covered only by
    # normative/institutional text.
    p_views = {dim: case_dimension_view(PRIMARY_CASE, dim)
               for dim in GOVERNANCE_DIMENSIONS}
    normative_dims = [d for d in GOVERNANCE_DIMENSIONS
                      if p_views[d]["evidence_count"] > 0 and _normative_only(p_views[d])]
    if normative_dims:
        ids = sorted({t["evidence_id"] for d in normative_dims
                      for t in p_views[d]["evidence"]})
        findings.append({
            "finding_id": "CROSS_DIMENSION-recurring_evidence_limitation-ETHIOPIA",
            "pattern": "recurring_evidence_limitation",
            "scope": PRIMARY_CASE,
            "statement": (
                f"For {PRIMARY_CASE}, evidence on {len(normative_dims)} of the "
                f"covered dimensions ({', '.join(normative_dims)}) rests entirely "
                "on normative/institutional records; independent implementation or "
                "empirical evidence is not yet recorded for those dimensions."),
            "dimensions": normative_dims,
            "evidence_ids": ids,
            "dimension_counts": {d: len(p_views[d]["evidence"]) for d in normative_dims},
        })

    # no_causal_inference: explicit integrity boundary of the report.
    findings.append({
        "finding_id": "CROSS_DIMENSION-no_causal_inference",
        "pattern": "no_causal_inference",
        "scope": "all_cases",
        "statement": (
            "This report describes what the recorded evidence establishes. It does "
            "not infer causation and it produces no numeric governance scores, "
            "indices or rankings."),
        "dimensions": [],
        "evidence_ids": [],
        "dimension_counts": {},
    })
    return findings


# ---------------------------------------------------------------------------
# Corpus state and coverage
# ---------------------------------------------------------------------------

def _real_evidence_ids():
    return sorted(E.evidence_id for E in Evidence.select()
                  if E.data_status == 'real')


def _real_observation_ids():
    return sorted(O.observation_id for O in GovernanceObservation.select()
                  if O.data_status == 'real')


def _corpus_state():
    evidence_ids = _real_evidence_ids()
    obs_ids = _real_observation_ids()
    digest_input = ",".join(str(i) for i in evidence_ids) + "|" \
        + ",".join(str(i) for i in obs_ids)
    return {
        "sources": Source.select().where(
            Source.data_status == 'real').count(),
        "evidence": len(evidence_ids),
        "observations": len(obs_ids),
        "relations": EvidenceRelation.select().count(),
        "cases": available_cases(),
        "corpus_digest": hashlib.sha256(
            digest_input.encode('utf-8')).hexdigest(),
    }


def _coverage_rows(cases):
    rows = []
    for case in sorted(cases):
        for dim in GOVERNANCE_DIMENSIONS:
            view = case_dimension_view(case, dim)
            rows.append({
                "case": case,
                "dimension": dim,
                "evidence_status": view["evidence_status"],
                "evidence_count": view["evidence_count"],
                "source_count": view["source_count"],
                "observation_count": view["observation_count"],
                "confidence": view["confidence"],
            })
    return rows


def _dimension_summaries(cases, findings, comparative_findings):
    summaries = []
    for dim in GOVERNANCE_DIMENSIONS:
        cases_block = {}
        for case in sorted(cases):
            view = case_dimension_view(case, dim)
            cases_block[case] = {
                "evidence_status": view["evidence_status"],
                "evidence_count": view["evidence_count"],
                "source_count": view["source_count"],
                "observation_count": view["observation_count"],
                "confidence": view["confidence"],
            }
        summaries.append({
            "dimension": dim,
            "cases": cases_block,
            "finding_ids": sorted(
                f["finding_id"] for f in findings if f["dimension"] == dim),
            "comparative_finding_ids": sorted(
                f["finding_id"] for f in comparative_findings if f["dimension"] == dim),
        })
    return summaries


def _ethiopia_synthesis(cases, findings, comparative_findings,
                        cross_dimension_findings):
    eth_findings = [f for f in findings if f["jurisdiction"] == PRIMARY_CASE]
    status_counts = Counter(f["evidence_status"] for f in eth_findings)
    covered = sorted(f["dimension"] for f in eth_findings
                     if f["evidence_status"] != MISSING_STATUS)
    confs = [
        f["confidence"] for f in eth_findings
        if f["confidence"] is not None
    ]
    comparative_ids = sorted(
        f["finding_id"] for f in comparative_findings
        if PRIMARY_CASE in f["pair"])
    cross_ids = sorted(
        f["finding_id"] for f in cross_dimension_findings
        if f["scope"] in (PRIMARY_CASE, "all_cases"))
    return {
        "case": PRIMARY_CASE,
        "status_counts": {
            s: status_counts.get(s, 0)
            for s in ("supported", "partial", "conflicting", "missing_evidence")
        },
        "dimensions_with_coverage": covered,
        "confidence_average": (
            int(round(sum(confs) / len(confs))) if confs else None),
        "primary_finding_ids": sorted(f["finding_id"] for f in eth_findings),
        "comparative_finding_ids": comparative_ids,
        "cross_dimension_finding_ids": cross_ids,
        "limitations": [
            "Synthesis covers the primary case (Ethiopia) as of the current "
            "committed corpus; later evidence revisions change the report "
            "deterministically.",
        ],
    }


# ---------------------------------------------------------------------------
# Resolved research gaps (committed record)
# ---------------------------------------------------------------------------

def load_resolved_gaps():
    """Load the committed record of research gaps closed by later evidence."""
    if not os.path.exists(RESOLVED_GAPS_PATH):
        return []
    with open(RESOLVED_GAPS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

_METHODOLOGY = {
    "layers": {
        "evidence": "traceable records from the evidence corpus",
        "observation": "governance observations linked to evidence",
        "interpretation": "assessment text from governance observations (never "
                          "converted into evidence)",
        "finding": "deterministic statements derived from counts, status and claims",
        "limitation": "where the corpus cannot support a conclusion",
        "research_gap": "explicit statements of absent/insufficient coverage",
    },
    "confidence_rule": (
        "rounded mean of linked governance-observation confidence values "
        "(integers 1-5); None when no linked observation exists. This is a "
        "corpus-confidence summary, never a statistical certainty."
    ),
    "comparative_rule": (
        "support_relation is assigned only when both sides of the pair hold "
        "evidence; unequal/absent coverage is reported as an evidence_limitation "
        "finding with an explicit limitation."
    ),
    "integrity": [
        "no facts are invented; findings derive from the committed database",
        "no numeric governance scores, indices or rankings are produced",
        "missing_evidence is never a negative finding",
        "co-occurrence across dimensions is a pattern, never a causal claim",
    ],
    "determinism": (
        "the report is a pure function of the committed database; no timestamps "
        "or randomized content are emitted."
    ),
}

_LIMITATIONS = [
    "This report is generated deterministically from the current evidence "
    "corpus; it is not the final academic paper.",
    "missing_evidence reflects corpus coverage, not a negative assessment "
    "(absence of evidence is not evidence of absence).",
    "Evidence is predominantly normative; enforcement and field-level "
    "implementation are not independently evidenced across all dimensions.",
    "Confidence reflects linked research observations, not statistical "
    "significance.",
    "Comparative findings compare recorded evidence coverage; they are not "
    "scores, indices, or rankings.",
    "Cross-dimension patterns describe the distribution of evidence sources "
    "and record nothing about causation.",
    "The report is reproducible only while the committed manifests and "
    "database state remain unchanged.",
]


def build_findings_report(case=None, dimension=None):
    """Deterministic findings synthesis derived from the committed database.

    ``case`` filters to one jurisdiction; ``dimension`` filters to one of the
    12 governance dimensions. The full report is always computed first and the
    filters only shape the emitted arrays.
    """
    cases = available_cases()
    gap_index = _current_gaps_index()

    full_findings = [
        _cell_finding(c, dim, gap_index)
        for c in cases for dim in GOVERNANCE_DIMENSIONS
    ]
    full_comparative = _comparative_findings(cases, gap_index)
    full_cross_dimension = _cross_dimension_findings(cases)

    findings = list(full_findings)
    comparative_findings = list(full_comparative)
    cross_dimension_findings = list(full_cross_dimension)

    remaining = [
        {
            "gap_id": g["gap_id"],
            "category": g["category"],
            "scope": g["scope"],
            "jurisdiction": g["jurisdiction"],
            "dimension": g["dimension"],
            "evidence_status": g["evidence_status"],
            "priority_level": g["priority_level"],
            "priority_score": g["priority_score"],
        }
        for g in gap_index.values()
    ]
    remaining.sort(key=lambda g: g["gap_id"])

    # Filters (presentation only; the full report stays deterministic).
    if case is not None:
        findings = [f for f in findings if f["jurisdiction"] == case]
        comparative_findings = [
            f for f in comparative_findings if case in f["pair"]]
        cross_dimension_findings = [
            f for f in cross_dimension_findings
            if f["scope"] in (case, "all_cases")]
        remaining = [
            g for g in remaining
            if g["jurisdiction"] == case
            or (g["jurisdiction"] == CROSS_CASE_LABEL and case in
                _gap_affected(gap_index[g["gap_id"]]))
            or case == PRIMARY_CASE and g["category"] == "comparative_coverage"
        ]
    if dimension is not None:
        findings = [f for f in findings if f["dimension"] == dimension]
        comparative_findings = [
            f for f in comparative_findings if f["dimension"] == dimension]
        cross_dimension_findings = [
            f for f in cross_dimension_findings
            if dimension in f["dimensions"] or not f["dimensions"]]
        remaining = [g for g in remaining if g["dimension"] == dimension]

    ethiopia_synthesis = _ethiopia_synthesis(
        cases, findings, comparative_findings, cross_dimension_findings)

    coverage = _coverage_rows(cases)
    summaries = _dimension_summaries(
        cases, full_findings, full_comparative)

    return {
        "report_type": REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "note": (
            "Evidence Re-analysis & Research Findings Synthesis. A deterministic, "
            "evidence-backed layer describing what the current corpus establishes. "
            "This is not a final academic paper, a score, or a ranking."
        ),
        "methodology": _METHODOLOGY,
        "corpus_state": _corpus_state(),
        "cases": [case_summary(c) for c in sorted(cases)],
        "dimensions": summaries,
        "findings": findings,
        "comparative_findings": comparative_findings,
        "cross_dimension_findings": cross_dimension_findings,
        "ethiopia_synthesis": ethiopia_synthesis,
        "evidence_coverage": [
            r for r in coverage
            if (case is None or r["case"] == case)
            and (dimension is None or r["dimension"] == dimension)
        ],
        "resolved_research_gaps": load_resolved_gaps(),
        "remaining_research_gaps": remaining,
        "limitations": list(_LIMITATIONS),
    }


def _gap_affected(gap):
    return gap.get("affected_cases") or [gap["jurisdiction"]]


# ---------------------------------------------------------------------------
# Validation (spec: reproducible layer must validate against schema + database)
# ---------------------------------------------------------------------------

def validate_findings(report):
    """Validate a findings report against the schema and the committed database.

    Raises pydantic.ValidationError on schema violations and ValueError on
    database-integrity violations. Returns the parsed model on success.
    """
    model = FindingsReport(**report)

    current_gaps = discover_gaps()
    gap_by_id = {g["gap_id"]: g for g in current_gaps}

    # --- per-cell findings ---
    fids = []
    for f in report["findings"]:
        fids.append(f["finding_id"])
        if f["finding_type"] in ("supported_finding", "partial_finding",
                                 "conflicting_finding", "comparative_finding"):
            if not f["evidence_refs"]:
                raise ValueError(
                    f"Finding {f['finding_id']} of type {f['finding_type']} has "
                    "no evidence references.")
        if f["jurisdiction"] == CROSS_CASE_LABEL:
            raise ValueError(
                f"Per-cell finding {f['finding_id']} must not use the "
                "cross-case jurisdiction.")
        allowed_ids = _jurisdiction_evidence_ids(f["jurisdiction"], f["dimension"])
        for ref in f["evidence_refs"]:
            if ref["evidence_id"] not in allowed_ids:
                raise ValueError(
                    f"Finding {f['finding_id']}: evidence {ref['evidence_id']} "
                    "does not belong to the cell "
                    f"{f['jurisdiction']}|{f['dimension']}.")
        _validate_obs_refs(f["observation_refs"], f["jurisdiction"], f["dimension"])
        for rf in f["research_gap_refs"]:
            g = gap_by_id.get(rf["gap_id"])
            if not g:
                raise ValueError(
                    f"Finding {f['finding_id']}: unresolved research-gap "
                    f"reference {rf['gap_id']}.")
            if g["jurisdiction"] != f["jurisdiction"] or g["dimension"] != f["dimension"]:
                raise ValueError(
                    f"Finding {f['finding_id']}: gap {rf['gap_id']} is not a cell "
                    "gap for this finding.")
    if len(fids) != len(set(fids)):
        raise ValueError("Duplicate per-cell finding identifiers.")

    # --- comparative findings ---
    cids = []
    for f in report["comparative_findings"]:
        cids.append(f["finding_id"])
        if f["finding_type"] == "evidence_limitation" and f["evidence_refs"] \
                and not (f["comparison"]["ethiopia_evidence_ids"]
                         or f["comparison"]["comparator_evidence_ids"]):
            raise ValueError(
                f"Comparative finding {f['finding_id']} has evidence refs but an "
                "empty comparison block.")
        valid_cases = {"Ethiopia", "European Union", "Kenya"}
        for side, jlabel in (("ethiopia", f["pair"][0]), ("comparator", f["pair"][1])):
            ids = f["comparison"][f"{side}_evidence_ids"]
            allowed = _jurisdiction_evidence_ids(jlabel, f["dimension"])
            for eid in ids:
                if eid not in allowed:
                    raise ValueError(
                        f"Comparative finding {f['finding_id']}: evidence {eid} "
                        f"does not belong to {jlabel}|{f['dimension']}.")
            _validate_obs_refs([r for r in f["observation_refs"]
                                if _obs_in_cell(r, jlabel, f["dimension"])],
                               jlabel, f["dimension"])
        for rf in f["research_gap_refs"]:
            g = gap_by_id.get(rf["gap_id"])
            if not g:
                raise ValueError(
                    f"Comparative finding {f['finding_id']}: unresolved research-gap "
                    f"reference {rf['gap_id']}.")
    if len(cids) != len(set(cids)):
        raise ValueError("Duplicate comparative finding identifiers.")

    # --- cross-dimension findings ---
    xids = [f["finding_id"] for f in report["cross_dimension_findings"]]
    if len(xids) != len(set(xids)):
        raise ValueError("Duplicate cross-dimension finding identifiers.")

    # --- resolved research gaps (committed closure record) ---
    for rec in report["resolved_research_gaps"]:
        if rec["gap_id"] in gap_by_id:
            raise ValueError(
                f"Resolved gap {rec['gap_id']} is still present in discover_gaps(); "
                "the closure record is inconsistent with the database.")
        jlabel = rec["jurisdiction"]
        allowed = _jurisdiction_evidence_ids(jlabel, rec["dimension"])
        for eid in rec["resolving_evidence_ids"]:
            e = Evidence.get_or_none(Evidence.evidence_id == eid)
            if not e:
                raise ValueError(
                    f"Resolved gap {rec['gap_id']}: orphan evidence reference {eid}.")
            if eid not in allowed:
                raise ValueError(
                    f"Resolved gap {rec['gap_id']}: evidence {eid} is not in "
                    f"{jlabel}|{rec['dimension']}.")

    # --- remaining research gaps all resolve ---
    seen = set()
    for g in report["remaining_research_gaps"]:
        if g["gap_id"] not in gap_by_id:
            raise ValueError(f"Remaining gap {g['gap_id']} is not in discover_gaps().")
        worst = {l: i for i, l in enumerate(("high", "medium", "low"))}
        if g["priority_score"] != gap_by_id[g["gap_id"]]["priority_score"]:
            raise ValueError(f"Remaining gap {g['gap_id']} priority score drift.")
        seen.add(g["gap_id"])
    if len(seen) != len(report["remaining_research_gaps"]):
        raise ValueError("Duplicate remaining research-gap identifiers.")

    # --- corpus state digest ---
    state = report["corpus_state"]
    if state["corpus_digest"] != _corpus_state()["corpus_digest"]:
        raise ValueError("corpus_digest does not match the current database state.")

    return model


def _validate_obs_refs(obs_refs, jurisdiction, dimension):
    allowed = {o.observation_id for o in _cell_observations(jurisdiction, dimension)}
    for r in obs_refs:
        if r["observation_id"] not in allowed:
            raise ValueError(
                f"Observation ref {r['observation_id']} does not belong to "
                f"{jurisdiction}|{dimension}.")


def _obs_in_cell(ref, jurisdiction, dimension):
    return any(
        o.observation_id == ref["observation_id"]
        for o in _cell_observations(jurisdiction, dimension)
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def findings_to_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False)


def findings_to_markdown(report):
    """Deterministic human-readable rendering of the findings report."""
    lines = []
    lines.append("# Evidence Findings Synthesis")
    lines.append("")
    lines.append(report["note"])
    lines.append("")

    cs = report["corpus_state"]
    lines.append("## Corpus state")
    lines.append("")
    lines.append(f"- sources: {cs['sources']}")
    lines.append(f"- evidence: {cs['evidence']}")
    lines.append(f"- observations: {cs['observations']}")
    lines.append(f"- relations: {cs['relations']}")
    lines.append(f"- cases: {', '.join(cs['cases'])}")
    lines.append(f"- corpus digest: `{cs['corpus_digest']}`")
    lines.append("")

    lines.append("## Cases")
    lines.append("")
    for case in report["cases"]:
        lines.append(f"- **{case['jurisdiction']}**: {case['evidence_count']} evidence "
                     f"record(s) from {case['source_count']} source(s); dimensions "
                     f"with evidence: {', '.join(case['dimensions_with_evidence']) or 'none'}")
    lines.append("")

    findings = report["findings"]
    if findings:
        lines.append(f"## Findings by dimension ({len(findings)})")
        lines.append("")
        for dim in GOVERNANCE_DIMENSIONS:
            dim_f = [f for f in findings if f["dimension"] == dim]
            if not dim_f:
                continue
            lines.append(f"### {dim}")
            lines.append("")
            for f in dim_f:
                conf = f"{f['confidence']}/5" if f["confidence"] is not None else "n/a"
                lines.append(f"#### {f['finding_id']} — {f['finding_type']}")
                lines.append("")
                lines.append(f"- jurisdiction: `{f['jurisdiction']}` "
                             f"(status: {f['evidence_status']}, confidence: {conf})")
                lines.append(f"- statement: {f['statement']}")
                if f["evidence_refs"]:
                    lines.append("- evidence: "
                                 + ", ".join(f"ev{r['evidence_id']}"
                                             for r in f["evidence_refs"]))
                if f["observation_refs"]:
                    lines.append("- observations: "
                                 + ", ".join(f"obs{r['observation_id']}"
                                             for r in f["observation_refs"]))
                if f["limitations"]:
                    for lim in f["limitations"]:
                        lines.append(f"- limitation: {lim}")
                if f["research_gap_refs"]:
                    lines.append("- linked gaps: "
                                 + "; ".join(f"{r['gap_id']} ({r['priority_level']})"
                                             for r in f["research_gap_refs"]))
                lines.append("")

    comp = report["comparative_findings"]
    if comp:
        lines.append(f"## Comparative findings ({len(comp)})")
        lines.append("")
        for f in comp:
            lines.append(f"### {f['finding_id']}")
            lines.append("")
            lines.append(f"- pair: {' vs '.join(f['pair'])}  (dimension `{f['dimension']}`)")
            if f["support_relation"]:
                lines.append(f"- relation: {f['support_relation']}")
            lines.append(f"- statement: {f['statement']}")
            cb = f["comparison"]
            lines.append(f"- {cb['ethiopia_status']} (evidence "
                         + ", ".join(f"ev{i}" for i in cb["ethiopia_evidence_ids"])
                         + ") vs " + cb["comparator_status"] + " (evidence "
                         + (", ".join(f"ev{i}" for i in cb["comparator_evidence_ids"])
                            or "none") + ")")
            if f["limitations"]:
                for lim in f["limitations"]:
                    lines.append(f"- limitation: {lim}")
            lines.append("")

    xd = report["cross_dimension_findings"]
    if xd:
        lines.append(f"## Cross-dimension findings ({len(xd)})")
        lines.append("")
        for f in xd:
            lines.append(f"- **{f['pattern']}** ({f['scope']}): {f['statement']}")
        lines.append("")

    eth = report["ethiopia_synthesis"]
    lines.append(f"## Primary-case synthesis ({eth['case']})")
    lines.append("")
    lines.append(f"- status counts: {', '.join(f'{k}={v}' for k, v in eth['status_counts'].items())}")
    lines.append(f"- dimensions with coverage: {', '.join(eth['dimensions_with_coverage']) or 'none'}")
    if eth["confidence_average"] is not None:
        lines.append(f"- average observation confidence: {eth['confidence_average']}/5")
    lines.append("")

    resolved = report["resolved_research_gaps"]
    lines.append(f"## Resolved research gaps ({len(resolved)})")
    lines.append("")
    for rec in resolved:
        lines.append(f"- `{rec['gap_id']}` — resolved by evidence "
                     + ", ".join(f"ev{i}" for i in rec["resolving_evidence_ids"])
                     + f" ({rec['category']})")
    lines.append("")

    remaining = report["remaining_research_gaps"]
    if remaining:
        levels = Counter(g["priority_level"] for g in remaining)
        lines.append(f"## Remaining research gaps ({len(remaining)})")
        lines.append("")
        lines.append(f"- high: {levels.get('high', 0)}, medium: {levels.get('medium', 0)}, "
                     f"low: {levels.get('low', 0)}")
        lines.append("")
        for g in remaining:
            lines.append(f"- `{g['gap_id']}` ({g['priority_level']}, {g['category']}, "
                         f"scope {g['scope']}, case {g['jurisdiction']})")
        lines.append("")

    lines.append("## Limitations")
    lines.append("")
    for lim in report["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    return "\n".join(lines)