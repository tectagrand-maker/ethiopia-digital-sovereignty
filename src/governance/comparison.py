"""Step 7: Comparative Governance Analysis.

Extends the Step 6 matrix/baseline machinery into a reproducible multi-case
comparison across the 12 governance dimensions. Every cell of the report
explicitly distinguishes:

- supported evidence      (``evidence_status``: supported / partial)
- missing evidence        (``evidence_status``: missing_evidence)
- conflicting evidence    (``evidence_status``: conflicting, ``conflicts``)
- analytical interpretation (``interpretation`` / ``analytical_notes``,
                             taken from governance observations)
- research gaps           (``gaps``)

No scores, rankings, country values or causal conclusions are produced or
invented. Evidence remains traceable to source, locator and citation. The
report is deterministic and validated against a pydantic schema before
output.
"""

import csv
import io
import json
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from src.evidence.models import (
    Evidence, EvidenceRelation, GovernanceObservation,
    GOVERNANCE_DIMENSIONS, DataStatus,
)
from src.governance.matrix import (
    _derive_status, _jurisdiction_evidence_ids, _major_gaps,
    SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS,
)
from src.governance.analysis import _comparison_note

CONFLICTING_STATUS = "conflicting"
ANALYSIS_REPORT_TYPE = "comparative_analysis"

VALID_STATUSES = {
    SUPPORTED_STATUS, PARTIAL_STATUS, CONFLICTING_STATUS, MISSING_STATUS,
}


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

class EvidenceTrace(BaseModel):
    """Machine-readable provenance trace for one evidence record."""
    evidence_id: int
    source_id: int
    source_title: str
    source_type: str
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    claim: str
    evidence_basis: Optional[str] = None
    data_status: str
    citation: Optional[str] = None
    source_url: Optional[str] = None


class ConflictRef(BaseModel):
    """A recorded contradiction between two evidence records in the cell."""
    evidence_a: int
    evidence_b: int
    notes: Optional[str] = None


class CaseDimensionView(BaseModel):
    """One (case, dimension) cell of the comparative analysis."""
    jurisdiction: str
    dimension: str
    evidence_status: str
    evidence_count: int
    source_count: int
    observation_count: int
    confidence: Optional[int] = None
    evidence: List[EvidenceTrace] = []
    conflicts: List[ConflictRef] = []
    interpretation: List[str] = []
    analytical_notes: List[str] = []
    gaps: str = ""

    @field_validator('evidence_status')
    @classmethod
    def _check_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid evidence_status: {v!r}. "
                             f"Must be one of {sorted(VALID_STATUSES)}")
        return v


class CaseSummary(BaseModel):
    """High-level profile of one comparison case."""
    jurisdiction: str
    source_groups: List[str] = []
    source_count: int = 0
    evidence_count: int = 0
    dimensions_with_evidence: List[str] = []


class ComparativeDimension(BaseModel):
    """One governance dimension across all cases."""
    dimension: str
    cases: Dict[str, CaseDimensionView]
    comparison_notes: List[str] = []


class ComparativeAnalysisReport(BaseModel):
    """Schema for the full comparative analysis output."""
    report_type: str = ANALYSIS_REPORT_TYPE
    note: str
    cases: List[CaseSummary]
    dimensions: List[ComparativeDimension]

    @field_validator('dimensions')
    @classmethod
    def _cover_all_dimensions(cls, v):
        ids = [d.dimension for d in v]
        if sorted(ids) != sorted(GOVERNANCE_DIMENSIONS):
            raise ValueError(
                "Report must cover exactly the 12 governance dimensions."
            )
        return v

    @model_validator(mode='after')
    def _cases_match(self):
        jurisdictions = {c.jurisdiction for c in self.cases}
        for dim in self.dimensions:
            if set(dim.cases.keys()) != jurisdictions:
                raise ValueError(
                    f"Dimension {dim.dimension!r} case keys do not match "
                    "the report's case set."
                )
        return self


# ---------------------------------------------------------------------------
# Case discovery and profiles
# ---------------------------------------------------------------------------

def available_cases():
    """Sorted list of jurisdictions with at least one real evidence record or
    real governance observation."""
    ev = set(
        e.country_or_jurisdiction
        for e in Evidence.select(Evidence.country_or_jurisdiction)
        .where(Evidence.data_status == 'real')
    )
    obs = set(
        o.jurisdiction
        for o in GovernanceObservation.select(GovernanceObservation.jurisdiction)
        .where(GovernanceObservation.data_status == 'real')
    )
    return sorted(ev | obs)


def case_summary(jurisdiction):
    """Profile of a comparison case (evidence/source counts, covered dims)."""
    evs = [
        e for e in Evidence.select()
        if e.country_or_jurisdiction == jurisdiction and e.data_status == 'real'
    ]
    sources = {e.source.source_id for e in evs}
    groups = sorted({e.source.jurisdiction_group for e in evs
                     if e.source.jurisdiction_group})
    dims = {
        dim for dim in GOVERNANCE_DIMENSIONS
        if _jurisdiction_evidence_ids(jurisdiction, dim)
    }
    return {
        "jurisdiction": jurisdiction,
        "source_groups": groups,
        "source_count": len(sources),
        "evidence_count": len(evs),
        "dimensions_with_evidence": sorted(dims),
    }


# ---------------------------------------------------------------------------
# Cell construction
# ---------------------------------------------------------------------------

def _evidence_trace(e):
    return {
        "evidence_id": e.evidence_id,
        "source_id": e.source.source_id,
        "source_title": e.source.title,
        "source_type": e.source.source_type,
        "locator_type": e.locator_type,
        "locator_value": e.locator_value,
        "claim": e.claim,
        "evidence_basis": e.evidence_basis,
        "data_status": e.data_status,
        "citation": e.citation,
        "source_url": e.source.url,
    }


def _cell_evidence_rows(jurisdiction, dimension):
    ids = _jurisdiction_evidence_ids(jurisdiction, dimension)
    rows = []
    if ids:
        rows = list(Evidence.select().where(
            Evidence.evidence_id.in_(ids)
        ))
    rows.sort(key=lambda e: e.evidence_id)
    return rows


def _cell_observations(jurisdiction, dimension):
    rows = list(GovernanceObservation.select().where(
        (GovernanceObservation.jurisdiction == jurisdiction)
        & (GovernanceObservation.dimension == dimension)
        & (GovernanceObservation.data_status == 'real')
    ))
    rows.sort(key=lambda o: o.observation_id)
    return rows


def _cell_conflicts(evidence_ids):
    """Contradictions where BOTH endpoints belong to the same cell."""
    if not evidence_ids:
        return []
    id_set = set(evidence_ids)
    conflicts = []
    for rel in EvidenceRelation.select().where(
            EvidenceRelation.relation_type == 'contradicts'):
        a = rel.evidence_a.evidence_id
        b = rel.evidence_b.evidence_id
        if a in id_set and b in id_set:
            conflicts.append({"evidence_a": a, "evidence_b": b, "notes": rel.notes})
    conflicts.sort(key=lambda c: (c["evidence_a"], c["evidence_b"]))
    return conflicts


def case_dimension_view(jurisdiction, dimension):
    """Build one (case, dimension) cell with explicit categories.

    Returns a plain dict (validated via the pydantic schema on output)."""
    evidence_rows = _cell_evidence_rows(jurisdiction, dimension)
    obs_rows = _cell_observations(jurisdiction, dimension)

    source_ids = {e.source.source_id for e in evidence_rows}
    base_status = _derive_status(len(evidence_rows), len(source_ids))

    conflicts = _cell_conflicts([e.evidence_id for e in evidence_rows])
    status = CONFLICTING_STATUS if conflicts else base_status

    confidence = None
    vals = [o.confidence for o in obs_rows if o.confidence]
    if vals:
        confidence = int(round(sum(vals) / len(vals)))

    gaps = _major_gaps(dimension, evidence_rows, obs_rows)
    if conflicts:
        gaps = "Unresolved contradictions among linked evidence. " + gaps

    return {
        "jurisdiction": jurisdiction,
        "dimension": dimension,
        "evidence_status": status,
        "evidence_count": len(evidence_rows),
        "source_count": len(source_ids),
        "observation_count": len(obs_rows),
        "confidence": confidence,
        "evidence": [_evidence_trace(e) for e in evidence_rows],
        "conflicts": conflicts,
        "interpretation": [o.assessment for o in obs_rows if o.assessment],
        "analytical_notes": [o.analytical_notes for o in obs_rows if o.analytical_notes],
        "gaps": gaps,
    }


def _pairwise_note(view_a, view_b):
    """Reuse the Step 6 baseline heuristic for a cross-case comparison note."""
    def _adapter(view):
        status = ('evidence_available'
                  if view["evidence_status"] != MISSING_STATUS
                  else 'missing_evidence')
        confidence = [view["confidence"]] if view["confidence"] else []
        return {"status": status, "confidence": confidence}
    return _comparison_note(_adapter(view_a), _adapter(view_b))


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def comparative_analysis(cases=None):
    """Full comparative analysis across the 12 dimensions.

    ``cases`` defaults to every jurisdiction with real evidence or
    observations. Output is deterministic (sorted cases, fixed dimension
    order, sorted notes).
    """
    if cases is None:
        cases = available_cases()
    cases = sorted(set(cases))

    report = {
        "report_type": ANALYSIS_REPORT_TYPE,
        "note": (
            "Comparative governance analysis. Each cell distinguishes "
            "supported evidence, missing evidence, conflicting evidence, "
            "analytical interpretation and research gaps. This is not a "
            "ranking and never assigns scores."
        ),
        "cases": [case_summary(c) for c in cases],
        "dimensions": [],
    }

    for dimension in GOVERNANCE_DIMENSIONS:
        views = {c: case_dimension_view(c, dimension) for c in cases}
        notes = []
        for i in range(len(cases)):
            for j in range(i + 1, len(cases)):
                a, b = cases[i], cases[j]
                notes.append(f"{a} vs {b}: {_pairwise_note(views[a], views[b])}")
        report["dimensions"].append({
            "dimension": dimension,
            "cases": views,
            "comparison_notes": notes,
        })

    return report


def validate_report(report):
    """Validate a comparative analysis report against the output schema.

    Raises pydantic.ValidationError if the structure is invalid. Returns the
    parsed model on success.
    """
    return ComparativeAnalysisReport(**report)


def analysis_to_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False)


def analysis_to_csv(report):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "dimension", "jurisdiction", "evidence_status", "evidence_count",
        "source_count", "observation_count", "confidence", "evidence_ids",
        "conflict_evidence_pairs", "interpretation", "gaps",
    ])
    for dim in report["dimensions"]:
        for case in report["cases"]:
            j = case["jurisdiction"]
            view = dim["cases"][j]
            writer.writerow([
                dim["dimension"],
                j,
                view["evidence_status"],
                view["evidence_count"],
                view["source_count"],
                view["observation_count"],
                view["confidence"],
                json.dumps([e["evidence_id"] for e in view["evidence"]]),
                json.dumps(view["conflicts"]),
                json.dumps(view["interpretation"]),
                view["gaps"],
            ])
    return buf.getvalue()
