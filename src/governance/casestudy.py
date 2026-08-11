"""Step 8: Evidence-Backed Case Study Framework.

Builds a reproducible, research-ready case-study dossier for a jurisdiction on
top of the existing evidence, provenance, governance-dimension and
comparative-analysis architecture (Steps 6-7). It does NOT write the polished
academic case study; it produces the structured layer from which narrative
case-study writing can later be generated.

Analytical separation (never blurred):

- ``evidence``          -- traceable records from the evidence corpus
- ``observation``       -- governance observations linked to evidence
- ``interpretation``    -- assessment text from those observations
- ``analytical_note``   -- free-text notes attached to observations
- ``research_gap``      -- explicit statements of absent/insufficient corpus
                           coverage (never a negative finding)

Everything is derived from the database; no facts are invented. ``missing``
means the corpus lacks evidence -- absence of evidence is not evidence of
absence.
"""

import json
import os
from collections import Counter, OrderedDict, defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.evidence.models import (
    Evidence, GovernanceObservation, GOVERNANCE_DIMENSIONS, DataStatus,
)
from src.governance.matrix import SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS
from src.governance.comparison import (
    EvidenceTrace, ConflictRef, case_dimension_view, _cell_observations,
    available_cases, comparative_analysis,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CASES_MANIFEST = os.path.join(REPO_ROOT, 'data', 'cases', 'cases.json')

DOSSIER_TYPE = "case_study_dossier"
SCHEMA_VERSION = 1

VALID_STATUSES = {SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS, "conflicting"}


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

class CaseIdentity(BaseModel):
    jurisdiction: str
    title: str
    description: str
    source_groups: List[str] = []
    source_count: int = 0
    evidence_count: int = 0
    available_dimensions: List[str] = []
    coverage_summary: Dict[str, int] = {}


class ObservationRef(BaseModel):
    """A governance observation referenced by a dimension profile."""
    observation_id: int
    indicator: str
    observed_evidence: str
    evidence_ids: List[int] = []


class DimensionProfile(BaseModel):
    dimension: str
    evidence_status: str
    evidence_count: int
    source_count: int
    observation_count: int
    confidence: Optional[int] = None
    evidence: List[EvidenceTrace] = []
    observations: List[ObservationRef] = []
    interpretation: List[str] = []
    analytical_notes: List[str] = []
    conflicts: List[ConflictRef] = []
    research_gaps: List[str] = []

    @field_validator('evidence_status')
    @classmethod
    def _check_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid evidence_status: {v!r}.")
        return v


class SynthesisFinding(BaseModel):
    """A synthesis finding that MUST be backed by evidence references."""
    claim: str
    evidence_ids: List[int]
    source_ids: List[int]


class CaseSynthesis(BaseModel):
    major_supported_findings: List[SynthesisFinding] = []
    partial_findings: List[SynthesisFinding] = []
    conflicting_evidence: List[ConflictRef] = []
    missing_evidence_areas: List[str] = []
    cross_dimension_patterns: List[str] = []
    limitations: List[str] = []
    priority_research_gaps: List[str] = []


class ComparativeContext(BaseModel):
    """Reference to the Step 7 comparative baseline, not a duplication."""
    note: str
    available_comparators: List[str] = []
    dimension_notes: Dict[str, List[str]] = {}


class CaseStudyDossier(BaseModel):
    dossier_type: str = DOSSIER_TYPE
    schema_version: int = SCHEMA_VERSION
    case: CaseIdentity
    dimension_profiles: List[DimensionProfile]
    synthesis: CaseSynthesis
    comparative_context: ComparativeContext

    @field_validator('dimension_profiles')
    @classmethod
    def _cover_all_dimensions(cls, v):
        ids = [p.dimension for p in v]
        if sorted(ids) != sorted(GOVERNANCE_DIMENSIONS):
            raise ValueError("Dossier must contain exactly the 12 governance dimensions.")
        return v


# ---------------------------------------------------------------------------
# Case identity
# ---------------------------------------------------------------------------

def load_case_meta():
    """Load the committed case metadata manifest (jurisdiction -> meta dict)."""
    if not os.path.exists(CASES_MANIFEST):
        return {}
    with open(CASES_MANIFEST, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    return {e["jurisdiction"]: e for e in entries}


def case_identity(jurisdiction):
    """Deterministic case identity block for a jurisdiction."""
    meta = load_case_meta().get(jurisdiction, {})
    evs = [
        e for e in Evidence.select()
        if e.country_or_jurisdiction == jurisdiction and e.data_status == 'real'
    ]
    sources = {e.source.source_id for e in evs}
    groups = sorted({e.source.jurisdiction_group for e in evs
                     if e.source.jurisdiction_group})
    available = [
        dim for dim in GOVERNANCE_DIMENSIONS
        if case_dimension_view(jurisdiction, dim)["evidence_count"] > 0
    ]
    status_counts = Counter()
    for dim in GOVERNANCE_DIMENSIONS:
        status_counts[case_dimension_view(jurisdiction, dim)["evidence_status"]] += 1

    return {
        "jurisdiction": jurisdiction,
        "title": meta.get("title") or jurisdiction,
        "description": meta.get("description") or "",
        "source_groups": groups,
        "source_count": len(sources),
        "evidence_count": len(evs),
        "available_dimensions": available,
        "coverage_summary": {
            s: status_counts.get(s, 0)
            for s in (SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS, "conflicting")
        },
    }


# ---------------------------------------------------------------------------
# Dimension profiles
# ---------------------------------------------------------------------------

def _observation_refs(jurisdiction, dimension):
    refs = []
    for o in _cell_observations(jurisdiction, dimension):
        refs.append({
            "observation_id": o.observation_id,
            "indicator": o.indicator,
            "observed_evidence": o.observed_evidence,
            "evidence_ids": [eo.evidence.evidence_id for eo in o.evidence_links],
        })
    return refs


def dimension_profile(jurisdiction, dimension):
    """One governance-dimension profile, reusing the Step 7 cell view."""
    view = case_dimension_view(jurisdiction, dimension)
    gaps = []
    if view["gaps"]:
        gaps.append(view["gaps"])
    return {
        "dimension": dimension,
        "evidence_status": view["evidence_status"],
        "evidence_count": view["evidence_count"],
        "source_count": view["source_count"],
        "observation_count": view["observation_count"],
        "confidence": view["confidence"],
        "evidence": view["evidence"],
        "observations": _observation_refs(jurisdiction, dimension),
        "interpretation": view["interpretation"],
        "analytical_notes": view["analytical_notes"],
        "conflicts": view["conflicts"],
        "research_gaps": gaps,
    }


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def _finding_from_trace(trace):
    return {
        "claim": trace["claim"],
        "evidence_ids": [trace["evidence_id"]],
        "source_ids": [trace["source_id"]],
    }


def _cross_dimension_patterns(profiles):
    by_dim = {p["dimension"]: p for p in profiles}
    dim_by_source = defaultdict(set)
    for dim in GOVERNANCE_DIMENSIONS:
        for trace in by_dim[dim]["evidence"]:
            dim_by_source[trace["source_id"]].add(dim)

    patterns = []
    for source_id in sorted(dim_by_source):
        dims = [d for d in GOVERNANCE_DIMENSIONS if d in dim_by_source[source_id]]
        if len(dims) >= 2:
            patterns.append(
                f"Source {source_id} contributes evidence to {len(dims)} "
                f"dimensions: {', '.join(dims)}."
            )

    counts = Counter(p["evidence_status"] for p in profiles)
    patterns.append(
        f"{counts.get('supported', 0)} dimensions supported, "
        f"{counts.get('partial', 0)} partial, "
        f"{counts.get('conflicting', 0)} conflicting, "
        f"{counts.get('missing_evidence', 0)} missing_evidence."
    )
    return patterns


def _synthesis(jurisdiction, profiles):
    by_dim = {p["dimension"]: p for p in profiles}

    major = []
    partial = []
    for dim in GOVERNANCE_DIMENSIONS:
        cell = by_dim[dim]
        for trace in cell["evidence"]:
            finding = _finding_from_trace(trace)
            if cell["evidence_status"] == SUPPORTED_STATUS:
                major.append(finding)
            elif cell["evidence_status"] == PARTIAL_STATUS:
                partial.append(finding)

    conflicts = []
    for dim in GOVERNANCE_DIMENSIONS:
        conflicts.extend(by_dim[dim]["conflicts"])
    # deterministic: sort by (evidence_a, evidence_b)
    conflicts.sort(key=lambda c: (c["evidence_a"], c["evidence_b"]))

    missing_areas = [dim for dim in GOVERNANCE_DIMENSIONS
                     if by_dim[dim]["evidence_status"] == MISSING_STATUS]

    priority_gaps = [f"No evidence for dimension {dim}." for dim in missing_areas]
    for dim in GOVERNANCE_DIMENSIONS:
        cell = by_dim[dim]
        if cell["evidence_status"] in (SUPPORTED_STATUS, PARTIAL_STATUS) \
                and not cell["observations"]:
            priority_gaps.append(
                f"Dimension {dim} has evidence but no governance observation synthesizes it yet."
            )
    priority_gaps.append(
        "Corpus is predominantly normative (statutes); "
        "independent implementation and enforcement evidence is missing."
    )

    limitations = [
        "This dossier is generated deterministically from the current evidence "
        "corpus; it is not a final academic case study.",
        "missing_evidence reflects corpus coverage, not a negative finding "
        "(absence of evidence is not evidence of absence).",
        "Evidence is predominantly normative; enforcement and field-level "
        "implementation are not independently evidenced.",
        "No numerical governance scores or rankings are assigned.",
        "Comparative notes classify patterns from evidence confidence and must "
        "be read together with the interpretation text.",
    ]

    return {
        "major_supported_findings": major,
        "partial_findings": partial,
        "conflicting_evidence": conflicts,
        "missing_evidence_areas": missing_areas,
        "cross_dimension_patterns": _cross_dimension_patterns(profiles),
        "limitations": limitations,
        "priority_research_gaps": priority_gaps,
    }


# ---------------------------------------------------------------------------
# Comparative context (reference only, no duplication)
# ---------------------------------------------------------------------------

def _comparative_context(jurisdiction, comparators):
    all_cases = available_cases()
    if comparators is None:
        comparators = [c for c in all_cases if c != jurisdiction]
    comparators = sorted(set(comparators))

    note = (
        "Comparative context references the Step 7 comparative baseline "
        f"(`python -m src.cli comparative --cases {jurisdiction},"
        f"{','.join(comparators)}`). It is a reference, not a duplication of "
        "the baseline report."
    )

    dimension_notes = {}
    if comparators:
        report = comparative_analysis([jurisdiction] + comparators)
        for dim in report["dimensions"]:
            matching = []
            for n in dim["comparison_notes"]:
                pair = n.partition(": ")[0]
                sides = [s.strip() for s in pair.split(" vs ")]
                if jurisdiction in sides:
                    matching.append(n)
            if matching:
                dimension_notes[dim["dimension"]] = matching

    return {
        "note": note,
        "available_comparators": comparators,
        "dimension_notes": dimension_notes,
    }


# ---------------------------------------------------------------------------
# Dossier assembly
# ---------------------------------------------------------------------------

def case_study_dossier(jurisdiction, comparators=None):
    """Generate the deterministic, evidence-backed dossier for a jurisdiction."""
    identity = case_identity(jurisdiction)
    profiles = [dimension_profile(jurisdiction, dim) for dim in GOVERNANCE_DIMENSIONS]
    return {
        "dossier_type": DOSSIER_TYPE,
        "schema_version": SCHEMA_VERSION,
        "case": identity,
        "dimension_profiles": profiles,
        "synthesis": _synthesis(jurisdiction, profiles),
        "comparative_context": _comparative_context(jurisdiction, comparators),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_dossier(dossier):
    """Validate schema + database integrity of a dossier.

    Raises pydantic.ValidationError on schema violations and ValueError on
    database-integrity violations (orphan evidence references, jurisdiction
    mismatches, source mismatches). Returns the parsed model on success.
    """
    model = CaseStudyDossier(**dossier)

    jurisdiction = dossier["case"]["jurisdiction"]
    referenced = set()

    for profile in dossier["dimension_profiles"]:
        for trace in profile["evidence"]:
            referenced.add(trace["evidence_id"])
            e = Evidence.get_or_none(Evidence.evidence_id == trace["evidence_id"])
            if not e:
                raise ValueError(f"Orphan evidence reference: {trace['evidence_id']}")
            if e.country_or_jurisdiction != jurisdiction:
                raise ValueError(
                    f"Evidence {trace['evidence_id']} jurisdiction "
                    f"({e.country_or_jurisdiction}) does not match dossier case "
                    f"({jurisdiction})."
                )
            if trace["source_id"] != e.source.source_id:
                raise ValueError(
                    f"Evidence {trace['evidence_id']} source mismatch "
                    f"(trace {trace['source_id']} vs db {e.source.source_id})."
                )
        for obs in profile["observations"]:
            referenced.update(obs["evidence_ids"])

    for finding in (dossier["synthesis"]["major_supported_findings"]
                    + dossier["synthesis"]["partial_findings"]):
        for eid in finding["evidence_ids"]:
            referenced.add(eid)
        if not finding["evidence_ids"]:
            raise ValueError("Synthesis finding without evidence references.")

    for eid in sorted(referenced):
        e = Evidence.get_or_none(Evidence.evidence_id == eid)
        if not e:
            raise ValueError(f"Orphan evidence reference: {eid}")

    return model


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def dossier_to_json(dossier):
    return json.dumps(dossier, indent=2, ensure_ascii=False)


def dossier_to_markdown(dossier):
    """Deterministic human-readable rendering for later case-study writing."""
    lines = []
    case = dossier["case"]
    lines.append(f"# Case Study Dossier: {case['title']}")
    lines.append("")
    if case["description"]:
        lines.append(case["description"])
        lines.append("")
    lines.append("## Case identity")
    lines.append("")
    lines.append(f"- jurisdiction: `{case['jurisdiction']}`")
    lines.append(f"- evidence coverage: {case['evidence_count']} evidence records "
                 f"from {case['source_count']} sources")
    lines.append(f"- available dimensions: {', '.join(case['available_dimensions']) or 'none'}")
    lines.append("")

    for profile in dossier["dimension_profiles"]:
        lines.append(f"## {profile['dimension']} — {profile['evidence_status']}")
        lines.append("")
        if profile["evidence"]:
            lines.append("### Evidence")
            for t in profile["evidence"]:
                loc = f"{t['locator_type']}:{t['locator_value']}" if t["locator_type"] else "no locator"
                lines.append(f"- [ev{t['evidence_id']}] {t['claim']} "
                             f"(_source {t['source_id']}, {loc}_")
            lines.append("")
        if profile["interpretation"]:
            lines.append("### Interpretation")
            for text in profile["interpretation"]:
                lines.append(f"- {text}")
            lines.append("")
        if profile["research_gaps"]:
            lines.append("### Research gaps")
            for text in profile["research_gaps"]:
                lines.append(f"- {text}")
            lines.append("")

    syn = dossier["synthesis"]
    lines.append("## Synthesis")
    lines.append("")
    lines.append(f"- major supported findings: {len(syn['major_supported_findings'])}")
    lines.append(f"- partial findings: {len(syn['partial_findings'])}")
    lines.append(f"- conflicting evidence: {len(syn['conflicting_evidence'])}")
    lines.append(f"- missing-evidence areas: {', '.join(syn['missing_evidence_areas']) or 'none'}")
    lines.append("")
    lines.append("### Priority research gaps")
    for g in syn["priority_research_gaps"]:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("## Comparative context")
    lines.append("")
    lines.append(dossier["comparative_context"]["note"])
    lines.append("")
    return "\n".join(lines)
