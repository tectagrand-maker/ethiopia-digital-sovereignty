"""Step 13: Evidence-Backed Academic Research Draft.

Assembles the first **research working-paper draft** from the verified research
infrastructure built in Steps 6-12. The draft is a *computed view*, not a new
data model: it re-uses the committed evidence corpus, the Step 7 comparative
baseline, the Step 8 dossier, the Step 9 research-gap plan, the Step 11
findings synthesis and the Step 12 narrative, and it adds **no** evidence of
its own.

Research-integrity rules preserved from the project's evidence policy:

- No sources, citations, statistics, quotes or theory are fabricated. Every
  number, count and citation in the draft derives from the committed database
  or the committed manifests.
- Every substantive analytical statement carries its ``evidence_ids`` and a
  ``statement_origin`` from the controlled vocabulary
  (``evidence_derived | analytical_interpretation | corpus_limitation``).
  Statements with no evidence are explicit corpus limitations, never verdicts.
- ``missing_evidence`` is a statement about the corpus, never a negative
  assessment of a jurisdiction.
- The draft assigns no scores, indices or rankings and makes no causal claims.
- Concentration of evidence across dimensions is reported as a distributional
  pattern, never as causation.
- Case-selection rationale is derived from the corpus; wherever it is
  incomplete it is explicitly marked as a limitation.
- The draft is deterministic: identical database state produces byte-identical
  JSON and Markdown. No timestamps, machine paths or randomized content are
  emitted.

The output is explicitly **not** automatically validated scholarly truth and
**not** a final publication: it is an evidence-backed research draft —
structured for a later human peer-review and publication phase, keeping every
sentence traceable so that the writing process never loses its provenance.
"""

import hashlib
import json
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from src.evidence.models import (
    Source, Evidence, EvidenceRelation, GovernanceObservation,
    GOVERNANCE_DIMENSIONS,
)
from src.governance.narrative import (
    case_study_narrative,
    NarrativeSection, ComparativeSection, CrossCuttingPattern,
    SynthesisBlock, ResearchGuidance, NarrativeClaim,
)
from src.governance.findings import (
    STATEMENT_ORIGINS, _jurlabel,
)
from src.governance.comparison import (
    available_cases, case_dimension_view,
)
from src.governance.matrix import _jurisdiction_evidence_ids
from src.governance.research_gaps import (
    PRIMARY_CASE, NORMATIVE_BASES, discover_gaps,
    RESEARCH_QUESTION_TEMPLATES, RECOMMENDED_SOURCE_TYPES,
)

ACADEMIC_TYPE = "academic_research_draft"
SCHEMA_VERSION = 1

VALID_STATUSES = {
    "supported", "partial", "missing_evidence", "conflicting",
}

# The integrity notice that must appear in the draft (docs/academic-draft.md).
DRAFT_NOTICE = (
    "This is an evidence-backed research draft, not automatically validated "
    "scholarly truth or a final publication."
)

_EMPIRICAL_BASES = {"empirical", "implementation", "observational", "technical"}

# Assignment-like language that would fabricate a rating; disclaimers (the word
# "score" inside "no scores") are allowed and are not detection targets.
_SCORE_ASSIGNMENT_PATTERNS = (
    "scored", "ranked", "score of", "rank #", "ranked #", "score:",
)


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

class AbstractBlock(BaseModel):
    statement: str
    scope_statement: str
    corpus_summary: Dict
    evidence_ids: List[int] = []

    @field_validator('scope_statement')
    @classmethod
    def _must_carry_notice(cls, v):
        if "not automatically validated scholarly truth" not in v:
            raise ValueError(
                "Abstract scope_statement must include the draft notice.")
        return v


class ResearchQuestion(BaseModel):
    question_id: str
    question: str
    source: str
    dimension: str = ""

    @field_validator('source')
    @classmethod
    def _check_source(cls, v):
        if v not in {"central_question", "research_guidance"}:
            raise ValueError(f"Invalid research-question source: {v!r}")
        return v

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v and v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @field_validator('question')
    @classmethod
    def _must_be_question(cls, v):
        if not v.endswith("?"):
            raise ValueError("research question must be phrased as a question")
        return v


class ResearchProblemBlock(BaseModel):
    research_problem: List[str]
    research_questions: List[ResearchQuestion]
    objectives: List[str]


class MethodologyBlock(BaseModel):
    approach: str
    data_layers: List[str]
    layer_separation: List[str]
    analytical_framework: List[str]
    pipeline_steps: List[str]
    integrity_statements: List[str]
    confidence_rule: str
    determinism: str


class CaseSelectionBlock(BaseModel):
    primary_case: str
    comparators: List[str]
    rationale: List[str]
    limitations: List[str]


class SourceRegisterEntry(BaseModel):
    source_id: int
    title: str
    source_type: str
    publisher_or_author: str = ""
    jurisdiction: str = ""
    publication_date: Optional[str] = None
    url: Optional[str] = None
    citation: Optional[str] = None
    jurisdiction_group: str = ""
    access_date: Optional[str] = None
    evidence_count: int


class EvidenceDescription(BaseModel):
    corpus_state: Dict
    per_case: List[dict]
    source_register: List[SourceRegisterEntry]


class EthiopiaCaseStudy(BaseModel):
    case: dict
    coverage_summary: Dict[str, int]
    dimension_sections: List[NarrativeSection]
    synthesis: SynthesisBlock

    @field_validator('dimension_sections')
    @classmethod
    def _cover_all_dimensions(cls, v):
        ids = [sec.dimension for sec in v]
        if sorted(ids) != sorted(GOVERNANCE_DIMENSIONS):
            raise ValueError(
                "Case-study chapter must contain exactly the 12 governance "
                "dimensions.")
        if [sec.dimension for sec in v] != list(GOVERNANCE_DIMENSIONS):
            raise ValueError(
                "Case-study chapter must follow the fixed dimension order.")
        return v


class ComparativeAnalysis(BaseModel):
    comparative_sections: List[ComparativeSection] = []


class CrossDimensionFindings(BaseModel):
    cross_cutting_patterns: List[CrossCuttingPattern] = []


class DimensionDiscussion(BaseModel):
    dimension: str
    evidence_status: str
    claims: List[NarrativeClaim] = []
    open_questions: List[str] = []

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @field_validator('evidence_status')
    @classmethod
    def _check_status(cls, v):
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid evidence_status: {v!r}")
        return v


class DiscussionBlock(BaseModel):
    points: List[DimensionDiscussion]


class LimitationsBlock(BaseModel):
    limitations: List[str]


class GapsBlock(BaseModel):
    remaining_research_gaps: List[dict] = []
    research_guidance: List[ResearchGuidance] = []


class ConclusionBlock(BaseModel):
    claims: List[NarrativeClaim] = []
    what_is_established: List[str] = []
    what_is_not_established: List[str] = []
    scope_notice: str

    @field_validator('scope_notice')
    @classmethod
    def _must_carry_notice(cls, v):
        if "not automatically validated scholarly truth" not in v:
            raise ValueError(
                "Conclusion scope_notice must include the draft notice.")
        return v


class TraceabilityRow(BaseModel):
    evidence_id: int
    section_id: str
    dimension: str
    source_id: int = 0
    claim: str = ""


class AcademicDraft(BaseModel):
    academic_type: str = ACADEMIC_TYPE
    schema_version: int = SCHEMA_VERSION
    title: str
    note: str
    abstract: AbstractBlock
    research_problem: ResearchProblemBlock
    methodology: MethodologyBlock
    case_selection: CaseSelectionBlock
    evidence_description: EvidenceDescription
    ethiopia_case_study: EthiopiaCaseStudy
    comparative_analysis: ComparativeAnalysis
    cross_dimension_findings: CrossDimensionFindings
    discussion: DiscussionBlock
    limitations: LimitationsBlock
    gaps: GapsBlock
    conclusion: ConclusionBlock
    traceability: List[TraceabilityRow] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _real_evidence_ids():
    return sorted(
        e.evidence_id for e in Evidence.select()
        if e.data_status == 'real')


def _corpus_summary():
    evidence_ids = _real_evidence_ids()
    obs_ids = sorted(
        o.observation_id for o in GovernanceObservation.select()
        if o.data_status == 'real')
    digest_input = ",".join(str(i) for i in evidence_ids) + "|" \
        + ",".join(str(i) for i in obs_ids)
    valid_ids = set(evidence_ids)
    sources_with_evidence = {
        e.source.source_id
        for e in Evidence.select()
        if e.data_status == 'real' and e.evidence_id in valid_ids
    }
    return {
        "sources_with_evidence": len(sources_with_evidence),
        "evidence": len(evidence_ids),
        "observations": len(obs_ids),
        "relations": EvidenceRelation.select().count(),
        "cases": available_cases(),
        "corpus_digest": hashlib.sha256(
            digest_input.encode('utf-8')).hexdigest(),
    }


def _source_evidence_count(source_id):
    return sum(
        1 for e in Evidence.select()
        if e.source.source_id == source_id and e.data_status == 'real')


def _source_register():
    entries = []
    for s in Source.select().order_by(Source.source_id):
        if s.data_status != 'real':
            continue
        entries.append({
            "source_id": s.source_id,
            "title": s.title,
            "source_type": s.source_type,
            "publisher_or_author": s.publisher_or_author or "",
            "jurisdiction": s.jurisdiction or "",
            "publication_date": (str(s.publication_date)
                                 if s.publication_date else None),
            "url": s.url,
            "citation": s.citation,
            "jurisdiction_group": s.jurisdiction_group or "",
            "access_date": (str(s.access_date) if s.access_date else None),
            "evidence_count": _source_evidence_count(s.source_id),
        })
    entries.sort(key=lambda e: e["source_id"])
    return entries


def _remaining_gaps(jurisdiction):
    """Remaining research gaps touching the case (from discover_gaps())."""
    out = []
    for g in discover_gaps():
        if g["jurisdiction"] == jurisdiction or jurisdiction in g["affected_cases"]:
            out.append({
                "gap_id": g["gap_id"],
                "category": g["category"],
                "scope": g["scope"],
                "jurisdiction": g["jurisdiction"],
                "dimension": g["dimension"],
                "evidence_status": g["evidence_status"],
                "priority_level": g["priority_level"],
                "priority_score": g["priority_score"],
            })
    out.sort(key=lambda g: g["gap_id"])
    return out


def _per_case():
    rows = []
    for case in available_cases():
        evs = [
            e for e in Evidence.select()
            if e.country_or_jurisdiction == case and e.data_status == 'real'
        ]
        sources = {e.source.source_id for e in evs}
        dims = {
            dim for dim in GOVERNANCE_DIMENSIONS
            if _jurisdiction_evidence_ids(case, dim)
        }
        rows.append({
            "case": case,
            "source_count": len(sources),
            "evidence_count": len(evs),
            "dimensions_with_evidence": sorted(dims),
        })
    rows.sort(key=lambda r: r["case"])
    return rows


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _abstract(jurisdiction, coverage_summary, corpus_summary):
    ev = corpus_summary["evidence"]
    src = corpus_summary["sources_with_evidence"]
    obs = corpus_summary["observations"]
    covered = (coverage_summary.get("supported", 0)
               + coverage_summary.get("partial", 0)
               + coverage_summary.get("conflicting", 0))
    missing = coverage_summary.get("missing_evidence", 0)
    missing_text = (f"holds no recorded evidence for {missing} dimension"
                    if missing == 1
                    else f"holds no recorded evidence for {missing} dimensions")
    statement = (
        f"This research draft investigates digital sovereignty and data "
        f"governance in {jurisdiction} using the project's committed evidence "
        f"corpus. It is built on {ev} real evidence records from {src} "
        f"sources and {obs} governance observations covering the 12-dimension "
        f"governance framework. For {jurisdiction}, the corpus records "
        f"evidence for {covered} of the 12 governance dimensions and "
        f"{missing_text}. Every analytical "
        f"statement in this draft is traced to its evidence references; "
        f"statements without evidence are explicitly marked as corpus "
        f"limitations, never as verdicts. This draft assigns no scores, "
        f"indices or rankings and makes no causal claims."
    )
    return {
        "statement": statement,
        "scope_statement": DRAFT_NOTICE,
        "corpus_summary": corpus_summary,
        "evidence_ids": _real_evidence_ids(),
    }


def _research_problem(jurisdiction, case_description, guidance_items):
    problem = [
        (
            f"{jurisdiction} is building a digital-governance infrastructure "
            f"whose legal and institutional frame the committed corpus "
            f"documents. The research problem is to establish, from recorded "
            f"evidence, what that frame currently is and what it does not yet "
            f"establish."
        ),
    ]
    if case_description:
        problem.append(case_description)
    problem.append(
        "The corpus records legal and institutional text for most dimensions "
        "but only partial, single-source or absent evidence for others, so the "
        "research problem includes distinguishing established states from "
        "corpus coverage limits."
    )
    questions = [{
        "question_id": f"{_jurlabel(jurisdiction)}-central-question",
        "question": (
            f"How is digital sovereignty and data governance constituted in "
            f"{jurisdiction}, based on the recorded evidence corpus, and what "
            f"does the corpus not yet establish?"
        ),
        "source": "central_question",
        "dimension": "",
    }]
    for dim in sorted({g["dimension"] for g in guidance_items}):
        cat = next(
            (g["category"] for g in guidance_items
             if g["dimension"] == dim), "evidence_coverage")
        sources = ", ".join(
            sorted(RECOMMENDED_SOURCE_TYPES.get(cat, [])))
        q = RESEARCH_QUESTION_TEMPLATES[cat].format(
            jurisdiction=jurisdiction, dimension=dim, sources=sources)
        questions.append({
            "question_id": f"{_jurlabel(jurisdiction)}-{dim}-guidance-question",
            "question": q,
            "source": "research_guidance",
            "dimension": dim,
        })
    objectives = [
        "Document, from the committed corpus, the state recorded for each of "
        "the 12 governance dimensions in the primary case.",
        "Surface explicitly what the corpus does not establish, without "
        "negative verdicts (missing_evidence is never a score).",
        "Compare the primary case with comparators only where both sides hold "
        "recorded evidence, and mark unequal coverage as a limitation.",
        "Produce a traceable draft in which every substantive statement maps "
        "to evidence ids and a statement origin, preserving provenance for a "
        "later peer-reviewed publication phase.",
    ]
    return {
        "research_problem": problem,
        "research_questions": questions,
        "objectives": objectives,
    }


def _methodology():
    layers = [
        "evidence: traceable records from the evidence corpus",
        "observation: governance observations linked to evidence",
        "interpretation: assessment text from governance observations "
        "(never converted into evidence)",
        "finding: deterministic statements derived from counts, status and "
        "claims",
        "limitation: where the corpus cannot support a conclusion",
        "research_gap: explicit statements of absent/insufficient coverage",
    ]
    separation = [
        "evidence claims come from evidence records",
        "interpretation text comes from governance observations and is never "
        "silently converted into evidence",
        "limitations explicitly mark where the corpus cannot support a "
        "conclusion",
        "research gaps are statements of what should be researched, not "
        "completed research",
    ]
    framework = [
        "a fixed analytical framework of 12 governance dimensions",
        "a statement_origin vocabulary: evidence_derived, "
        "analytical_interpretation, corpus_limitation",
        "evidence_basis classification (normative, institutional, technical, "
        "empirical, implementation, observational)",
        "data_status separation: real vs synthetic vs methodological",
    ]
    steps = [
        "Step 6 Evidence Matrix and comparative baseline",
        "Step 7 Comparative Governance Analysis",
        "Step 8 Case-Study Dossier",
        "Step 9 Research Gap Prioritization",
        "Step 11 Evidence Findings Synthesis",
        "Step 12 Evidence-Traceable Case-Study Narrative",
        "Step 13 Academic Research Draft (this document)",
    ]
    integrity = [
        "no sources, citations, statistics, quotes or theory are fabricated",
        "every substantive statement carries evidence ids and a statement "
        "origin",
        "missing_evidence is a corpus statement, never a negative finding",
        "no scores, indices or rankings are assigned",
        "no causal claims are made from evidence distribution or "
        "co-occurrence",
        "case-selection rationale is corpus-derived and marked as limited "
        "where incomplete",
    ]
    confidence_rule = (
        "confidence is the rounded mean of linked governance-observation "
        "confidence values (integers 1-5); None when no linked observation "
        "exists. It is a corpus-confidence summary, never statistical "
        "certainty."
    )
    determinism = (
        "the draft is a pure function of the committed database and committed "
        "manifests; identical state produces byte-identical JSON and Markdown, "
        "and no timestamps, machine paths or randomized content are emitted."
    )
    return {
        "approach": (
            "A reproducible, evidence-based research infrastructure in which "
            "a SQLite evidence database is rebuilt deterministically from "
            "committed manifests, and every analytical layer (baseline, "
            "dossier, gaps, findings, narrative, draft) is a computed view "
            "over that database."
        ),
        "data_layers": layers,
        "layer_separation": separation,
        "analytical_framework": framework,
        "pipeline_steps": steps,
        "integrity_statements": integrity,
        "confidence_rule": confidence_rule,
        "determinism": determinism,
    }


def _case_selection(jurisdiction, comparators):
    rationale = [
        f"{jurisdiction} is the primary case of the research program, as set "
        "out in the project's coverage matrix and case-study pipeline "
        "(PRIMARY_CASE in the research-gap framework).",
    ]
    if comparators:
        labelled = ", ".join(comparators)
        rationale.append(
            f"The comparators are {labelled}: cases for which the corpus "
            "records data-protection or digital-governance evidence, selected "
            "for their documented regulatory regimes."
        )
    rationale.append(
        "Comparative statements are limited to dimensions where both sides of "
        "a pair hold recorded evidence; unequal or absent coverage is never "
        "presented as a conclusion."
    )
    limitations = []
    if comparators:
        limitations.append(
            "Comparator evidence bases are narrow: most comparator dimension "
            "cells are missing_evidence, which limits the breadth of the "
            "comparative analysis in this draft."
        )
    limitations.append(
        "Case-selection rationale is derived from the current committed "
        "corpus and the project brief; a fuller scholarly justification of "
        "case choice is outside the scope of this corpus-derived draft."
    )
    return {
        "primary_case": jurisdiction,
        "comparators": sorted(comparators),
        "rationale": rationale,
        "limitations": limitations,
    }


def _discussion(jurisdiction, narrative):
    """Per-dimension discussion points reusing the Step 12 narrative claims."""
    sections_by_dim = {
        sec["dimension"]: sec
        for sec in narrative["dimension_sections"]
    }
    guidance_by_dim = {}
    for item in narrative["research_guidance"]:
        guidance_by_dim.setdefault(item["dimension"], []).append(item)

    points = []
    for dim in GOVERNANCE_DIMENSIONS:
        sec = sections_by_dim[dim]
        status = sec["evidence_status"]
        claims = []
        for i, claim in enumerate(sec["narrative"], start=1):
            claims.append({
                "claim_id": f"{_jurlabel(jurisdiction)}-{dim}-"
                            f"discussion-{i:02d}",
                "statement": claim["statement"],
                "statement_origin": claim["statement_origin"],
                "evidence_ids": list(claim["evidence_ids"]),
            })
        view = case_dimension_view(jurisdiction, dim)
        traces = view["evidence"]
        if traces:
            bases = {t["evidence_basis"] for t in traces if t["evidence_basis"]}
            normative = sorted(bases & NORMATIVE_BASES)
            empirical = sorted(bases & _EMPIRICAL_BASES)
            parts = [f"Evidence for '{dim}' in {jurisdiction} comprises "
                     f"{len(traces)} record(s)."]
            if normative:
                parts.append(f"Normative/institutional basis classes: "
                             f"{', '.join(normative)}.")
            if empirical:
                parts.append(f"Empirical/implementation/observational/technical "
                             f"basis classes: {', '.join(empirical)}.")
            if bases and not (bases & _EMPIRICAL_BASES):
                parts.append("The recorded basis is normative-only, so "
                             "field-level implementation is not independently "
                             "evidenced.")
            claims.append({
                "claim_id": f"{_jurlabel(jurisdiction)}-{dim}-discussion-basis",
                "statement": " ".join(parts),
                "statement_origin": "analytical_interpretation",
                "evidence_ids": [t["evidence_id"] for t in traces],
            })
        open_questions = [
            item["research_question"]
            for item in guidance_by_dim.get(dim, [])
        ]
        points.append({
            "dimension": dim,
            "evidence_status": status,
            "claims": claims,
            "open_questions": open_questions,
        })
    return {"points": points}


def _conclusion(jurisdiction, dim_statuses, status_counts,
                missing_dims, conflict_dims):
    claims = []
    seq = 0

    def _next():
        nonlocal seq
        seq += 1
        return f"{_jurlabel(jurisdiction)}-conclusion-{seq:02d}"

    joined = sorted({
        eid for dim in GOVERNANCE_DIMENSIONS
        for eid in _jurisdiction_evidence_ids(jurisdiction, dim)
    })
    supported = status_counts.get("supported", 0)
    partial = status_counts.get("partial", 0)
    claims.append({
        "claim_id": _next(),
        "statement": (
            f"The recorded corpus establishes {supported} governance "
            f"dimension(s) for {jurisdiction} as supported and {partial} as "
            "partially evidenced."
        ),
        "statement_origin": "evidence_derived",
        "evidence_ids": joined,
    })
    for dim in GOVERNANCE_DIMENSIONS:
        if dim in missing_dims:
            continue
        ids = _jurisdiction_evidence_ids(jurisdiction, dim)
        if ids:
            claims.append({
                "claim_id": _next(),
                "statement": (
                    f"Dimension '{dim}' is established in the corpus by "
                    f"{len(ids)} evidence record(s) (status "
                    f"{dim_statuses[dim]})."
                ),
                "statement_origin": "evidence_derived",
                "evidence_ids": ids,
            })
    claims.append({
        "claim_id": _next(),
        "statement": (
            "This draft establishes what the current corpus records and "
            "explicitly leaves its limits visible; it does not infer "
            "causation and it assigns no scores, indices or rankings."
        ),
        "statement_origin": "corpus_limitation",
        "evidence_ids": [],
    })

    established = [
        f"Dimension '{dim}' is supported by the current corpus."
        for dim, st in dim_statuses.items() if st == "supported"
    ]
    not_established = []
    for dim in missing_dims:
        not_established.append(
            f"Dimension '{dim}' has no recorded evidence in the current "
            "corpus (missing coverage is not a negative assessment).")
    for dim, st in dim_statuses.items():
        if st == "partial":
            not_established.append(
                f"Dimension '{dim}' is only partially evidenced and not fully "
                "triangulated.")
    for dim, conflicts in sorted(conflict_dims.items()):
        if conflicts:
            not_established.append(
                f"Dimension '{dim}' holds recorded, unresolved conflicting "
                "evidence.")

    return {
        "claims": claims,
        "what_is_established": established,
        "what_is_not_established": not_established,
        "scope_notice": DRAFT_NOTICE,
    }


def _limitations():
    return [
        "This draft is generated deterministically from the current "
        "committed corpus; later evidence revisions change the report "
        "deterministically.",
        "missing_evidence reflects corpus coverage, never a negative "
        "assessment (absence of evidence is not evidence of absence).",
        "Evidence is predominantly normative; enforcement and field-level "
        "implementation are not independently evidenced across all "
        "dimensions.",
        "Confidence reflects linked research observations, not statistical "
        "significance.",
        "Comparative sections compare recorded evidence coverage; they are "
        "not scores, indices or rankings.",
        "Cross-dimension patterns describe the distribution of evidence "
        "sources and record nothing about causation.",
        DRAFT_NOTICE,
    ]


# ---------------------------------------------------------------------------
# Traceability appendix
# ---------------------------------------------------------------------------

def _evidence_claim_text(eid):
    e = Evidence.get_or_none(Evidence.evidence_id == eid)
    return e.claim if e else ""


def _traceability(academic_draft):
    rows = []
    seen = set()
    refs = _referenced_sections(academic_draft)
    for eid in sorted(refs):
        e = Evidence.get_or_none(Evidence.evidence_id == eid)
        dimension = _traceability_dimension(academic_draft, eid)
        for section_id in sorted(refs[eid]):
            key = (eid, section_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "evidence_id": eid,
                "section_id": section_id,
                "dimension": dimension,
                "source_id": (e.source.source_id if e else 0),
                "claim": _evidence_claim_text(eid),
            })
    rows.sort(key=lambda r: (r["evidence_id"], r["section_id"]))
    return rows


def _referenced_sections(academic_draft):
    """Map each referenced evidence id to the section ids that cite it."""
    referenced = {}

    def _add(eid, section_id):
        if not eid:
            return
        referenced.setdefault(eid, set()).add(section_id)

    for eid in academic_draft["abstract"]["evidence_ids"]:
        _add(eid, "abstract")
    for sec in academic_draft["ethiopia_case_study"]["dimension_sections"]:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                _add(eid, f"case_study:{sec['section_id']}")
    for sec in academic_draft["comparative_analysis"]["comparative_sections"]:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                _add(eid, f"comparative:{sec['section_id']}")
    for p in academic_draft["cross_dimension_findings"][
            "cross_cutting_patterns"]:
        for eid in p["evidence_ids"]:
            _add(eid, f"cross-cutting:{p['pattern']}")
    for point in academic_draft["discussion"]["points"]:
        for claim in point["claims"]:
            for eid in claim["evidence_ids"]:
                _add(eid, f"discussion:{point['dimension']}")
    for claim in academic_draft["conclusion"]["claims"]:
        for eid in claim["evidence_ids"]:
            _add(eid, "conclusion")
    return referenced


def _traceability_dimension(academic_draft, eid):
    """Dimension label applied to a traceability row for the given evidence."""
    for sec in academic_draft["ethiopia_case_study"]["dimension_sections"]:
        for claim in sec["narrative"]:
            if eid in claim["evidence_ids"]:
                return sec["dimension"]
    for sec in academic_draft["comparative_analysis"]["comparative_sections"]:
        for claim in sec["narrative"]:
            if eid in claim["evidence_ids"]:
                return sec["dimension"]
    for p in academic_draft["cross_dimension_findings"][
            "cross_cutting_patterns"]:
        if eid in p["evidence_ids"]:
            return ";".join(p["dimensions"]) or p["scope"]
    for point in academic_draft["discussion"]["points"]:
        for claim in point["claims"]:
            if eid in claim["evidence_ids"]:
                return point["dimension"]
    return ""


# ---------------------------------------------------------------------------
# Draft assembly
# ---------------------------------------------------------------------------

def build_academic_draft(case=None, comparators=None):
    """Deterministic, evidence-backed academic research draft (Step 13).

    ``case`` defaults to the primary case (Ethiopia); ``comparators`` defaults
    to every other available case. The draft is a pure function of the
    committed database and committed manifests.
    """
    jurisdiction = case or PRIMARY_CASE
    if jurisdiction not in available_cases():
        raise ValueError(
            f"Unknown case {jurisdiction!r}; available cases are "
            f"{sorted(available_cases())}.")
    all_cases = available_cases()
    if comparators is None:
        comparators = [c for c in all_cases if c != jurisdiction]
    comparators = sorted(set(comparators))

    narrative = case_study_narrative(jurisdiction, comparators)

    case_meta = narrative["case"]  # identical to the Step 8 dossier case block
    coverage_summary = case_meta["coverage_summary"]

    dim_statuses = {
        sec["dimension"]: sec["evidence_status"]
        for sec in narrative["dimension_sections"]
    }
    status_counts = {}
    for st in dim_statuses.values():
        status_counts[st] = status_counts.get(st, 0) + 1

    conflict_dims = {}
    for dim in GOVERNANCE_DIMENSIONS:
        conflicts = case_dimension_view(jurisdiction, dim)["conflicts"]
        if conflicts:
            conflict_dims[dim] = conflicts

    missing_dims = [dim for dim, st in dim_statuses.items()
                    if st == "missing_evidence"]

    corpus_summary = _corpus_summary()
    guidance = narrative["research_guidance"]

    title = ("Research Draft: Digital Sovereignty and Data Governance "
             f"in {jurisdiction}")

    draft = {
        "academic_type": ACADEMIC_TYPE,
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "note": (
            "Evidence-backed academic research draft generated deterministically"
            " from the committed research infrastructure (Steps 6-12). Every "
            "substantive statement is traceable to evidence ids and a statement "
            "origin; statements without evidence are explicit corpus "
            "limitations. "
            + DRAFT_NOTICE
        ),
        "abstract": _abstract(
            jurisdiction, coverage_summary, corpus_summary),
        "research_problem": _research_problem(
            jurisdiction, case_meta.get("description"), guidance),
        "methodology": _methodology(),
        "case_selection": _case_selection(jurisdiction, comparators),
        "evidence_description": {
            "corpus_state": corpus_summary,
            "per_case": _per_case(),
            "source_register": _source_register(),
        },
        "ethiopia_case_study": {
            "case": case_meta,
            "coverage_summary": coverage_summary,
            "dimension_sections": narrative["dimension_sections"],
            "synthesis": narrative["synthesis"],
        },
        "comparative_analysis": {
            "comparative_sections": narrative["comparative_sections"],
        },
        "cross_dimension_findings": {
            "cross_cutting_patterns": narrative["cross_cutting_patterns"],
        },
        "discussion": _discussion(jurisdiction, narrative),
        "limitations": {
            "limitations": _limitations()
            + list(narrative["limitations"]),
        },
        "gaps": {
            "remaining_research_gaps": _remaining_gaps(jurisdiction),
            "research_guidance": guidance,
        },
        "conclusion": _conclusion(
            jurisdiction, dim_statuses, status_counts,
            missing_dims, conflict_dims,
        ),
        "traceability": [],
    }
    draft["traceability"] = _traceability(draft)
    return draft


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_academic_draft(draft):
    """Validate an academic draft against its schema and the committed database.

    Raises pydantic.ValidationError on schema violations and ValueError on
    database-integrity violations. Returns the parsed model on success.
    """
    model = AcademicDraft(**draft)
    jurisdiction = draft["ethiopia_case_study"]["case"]["jurisdiction"]

    # --- section completeness ---
    required_top = [
        "academic_type", "schema_version", "title", "note", "abstract",
        "research_problem", "methodology", "case_selection",
        "evidence_description", "ethiopia_case_study", "comparative_analysis",
        "cross_dimension_findings", "discussion", "limitations", "gaps",
        "conclusion", "traceability",
    ]
    for key in required_top:
        if key not in draft:
            raise ValueError(f"Academic draft missing required section: {key}")
    if not draft["abstract"]["statement"].strip():
        raise ValueError("Abstract statement must not be empty.")
    if not draft["research_problem"]["research_problem"]:
        raise ValueError("Research problem block must not be empty.")
    if not draft["research_problem"]["research_questions"]:
        raise ValueError("Research questions block must not be empty.")
    if not draft["methodology"]["pipeline_steps"]:
        raise ValueError("Methodology pipeline steps must not be empty.")

    # --- no orphan evidence references ---
    referenced = set()
    valid_ids = set(_real_evidence_ids())

    abstract_ids = draft["abstract"]["evidence_ids"]
    for eid in abstract_ids:
        if eid not in valid_ids:
            raise ValueError(f"Orphan abstract evidence reference: {eid}")
    referenced.update(abstract_ids)

    for sec in draft["ethiopia_case_study"]["dimension_sections"]:
        allowed = _jurisdiction_evidence_ids(jurisdiction, sec["dimension"])
        claim_ids = []
        for claim in sec["narrative"]:
            claim_ids.append(claim["claim_id"])
            for eid in claim["evidence_ids"]:
                referenced.add(eid)
                if eid not in valid_ids:
                    raise ValueError(f"Orphan evidence reference: {eid}")
                if eid not in allowed:
                    raise ValueError(
                        f"Case-study section {sec['section_id']}: evidence "
                        f"{eid} does not belong to the cell "
                        f"{jurisdiction}|{sec['dimension']}.")
            if claim["statement_origin"] != "corpus_limitation" \
                    and not claim["evidence_ids"]:
                raise ValueError(
                    f"Case-study claim {claim['claim_id']} has no evidence "
                    "references but is not a corpus limitation.")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError(
                f"Duplicate claim identifiers in {sec['section_id']}.")

    for sec in draft["comparative_analysis"]["comparative_sections"]:
        pair = set(sec["pair"])
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                referenced.add(eid)
                if eid not in valid_ids:
                    raise ValueError(f"Orphan evidence reference: {eid}")
                e = Evidence.get_or_none(Evidence.evidence_id == eid)
                if e and e.country_or_jurisdiction not in pair:
                    raise ValueError(
                        f"Comparative claim evidence {eid} belongs to "
                        f"{e.country_or_jurisdiction}, outside pair "
                        f"{sorted(pair)}.")

    cids = [s["section_id"]
            for s in draft["comparative_analysis"]["comparative_sections"]]
    if len(cids) != len(set(cids)):
        raise ValueError("Duplicate comparative section identifiers.")

    for p in draft["cross_dimension_findings"]["cross_cutting_patterns"]:
        for eid in p["evidence_ids"]:
            referenced.add(eid)
            if eid not in valid_ids:
                raise ValueError(f"Orphan evidence reference: {eid}")

    for point in draft["discussion"]["points"]:
        allowed = _jurisdiction_evidence_ids(jurisdiction, point["dimension"])
        for claim in point["claims"]:
            for eid in claim["evidence_ids"]:
                referenced.add(eid)
                if eid not in valid_ids:
                    raise ValueError(f"Orphan evidence reference: {eid}")
                if eid not in allowed:
                    raise ValueError(
                        f"Discussion evidence {eid} does not belong to the "
                        f"cell {jurisdiction}|{point['dimension']}.")

    for claim in draft["conclusion"]["claims"]:
        for eid in claim["evidence_ids"]:
            referenced.add(eid)
            if eid not in valid_ids:
                raise ValueError(f"Orphan evidence reference: {eid}")

    # --- all referenced evidence must exist ---
    for eid in sorted(referenced):
        if not Evidence.get_or_none(Evidence.evidence_id == eid):
            raise ValueError(f"Orphan evidence reference: {eid}")

    # --- research guidance resolves against the live gap inventory ---
    live = {g["gap_id"]: g for g in discover_gaps()}
    for item in draft["gaps"]["research_guidance"]:
        g = live.get(item["gap_id"])
        if not g:
            raise ValueError(
                f"Research guidance {item['gap_id']} is not in discover_gaps().")
        if jurisdiction not in (g["jurisdiction"], *g["affected_cases"]):
            raise ValueError(
                f"Research guidance {item['gap_id']} does not touch "
                f"{jurisdiction}.")
    for gap in draft["gaps"]["remaining_research_gaps"]:
        if gap["gap_id"] not in live:
            raise ValueError(
                f"Remaining gap {gap['gap_id']} is not in discover_gaps().")

    # --- source register integrity ---
    register = draft["evidence_description"]["source_register"]
    seen_sources = set()
    for entry in register:
        if entry["source_id"] in seen_sources:
            raise ValueError(f"Duplicate source-register entry: "
                             f"{entry['source_id']}.")
        seen_sources.add(entry["source_id"])
        s = Source.get_or_none(Source.source_id == entry["source_id"])
        if not s:
            raise ValueError(f"Source register references missing source: "
                             f"{entry['source_id']}.")
        if s.data_status != 'real':
            raise ValueError(
                f"Source register entry {entry['source_id']} is not real.")
        if entry["evidence_count"] != _source_evidence_count(entry["source_id"]):
            raise ValueError(
                f"Source register evidence_count drift for source "
                f"{entry['source_id']}.")

    # --- traceability appendix matches the references ---
    rows = draft["traceability"]
    row_ids = [(r["evidence_id"], r["section_id"]) for r in rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("Duplicate traceability rows.")
    row_evs = {r["evidence_id"] for r in rows}
    if row_evs != referenced:
        raise ValueError(
            "Traceability appendix evidence set does not match the evidence "
            "actually referenced in the draft.")
    referenced_sections = _referenced_sections(draft)
    for r in rows:
        if not Evidence.get_or_none(Evidence.evidence_id == r["evidence_id"]):
            raise ValueError(f"Traceability orphan evidence: {r['evidence_id']}.")
        if r["section_id"] not in referenced_sections.get(r["evidence_id"], set()):
            raise ValueError(
                f"Traceability manifests an unreferenced pair: ev"
                f"{r['evidence_id']} -> {r['section_id']}.")

    # --- no fabricated rating assignment inside draft-authored claims ---
    _check_no_scores(draft)

    return model


def _check_no_scores(draft):
    authored = []
    for point in draft["discussion"]["points"]:
        authored.extend(claim["statement"] for claim in point["claims"])
    for claim in draft["conclusion"]["claims"]:
        authored.append(claim["statement"])
    for text in authored:
        low = text.lower()
        for pat in _SCORE_ASSIGNMENT_PATTERNS:
            if pat in low:
                raise ValueError(
                    f"Rating-assignment language detected in draft claim: "
                    f"{text!r}")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def academic_to_json(draft):
    return json.dumps(draft, indent=2, ensure_ascii=False)


def academic_to_markdown(draft):
    """Deterministic human-readable rendering of the academic research draft."""
    lines = []
    lines.append(f"# {draft['title']}")
    lines.append("")
    lines.append(draft["note"])
    lines.append("")

    abs_ = draft["abstract"]
    lines.append("## Abstract")
    lines.append("")
    lines.append(abs_["statement"])
    cs = abs_["corpus_summary"]
    lines.append("")
    lines.append("**Corpus summary**")
    lines.append("")
    lines.append(f"- sources with evidence: {cs['sources_with_evidence']}")
    lines.append(f"- evidence records: {cs['evidence']}")
    lines.append(f"- governance observations: {cs['observations']}")
    lines.append(f"- relations: {cs['relations']}")
    lines.append(f"- cases: {', '.join(cs['cases'])}")
    lines.append(f"- corpus digest: `{cs['corpus_digest']}`")
    lines.append("")
    lines.append(f"_Scope notice: {abs_['scope_statement']}_")
    lines.append("")

    rp = draft["research_problem"]
    lines.append("## Research problem")
    lines.append("")
    for i, p in enumerate(rp["research_problem"], start=1):
        lines.append(f"{i}. {p}")
    lines.append("")
    lines.append("### Research questions")
    lines.append("")
    for q in rp["research_questions"]:
        src = "gap-derived" if q["source"] == "research_guidance" \
            else "central"
        tag = f" ({q['dimension']})" if q["dimension"] else ""
        lines.append(f"- {q['question']} _[{src}{tag}]_")
    lines.append("")
    lines.append("### Objectives")
    lines.append("")
    for o in rp["objectives"]:
        lines.append(f"- {o}")
    lines.append("")

    m = draft["methodology"]
    lines.append("## Methodology")
    lines.append("")
    lines.append(m["approach"])
    lines.append("")
    lines.append(f"- confidence rule: {m['confidence_rule']}")
    lines.append(f"- determinism: {m['determinism']}")
    lines.append("")
    lines.append("### Data layers")
    lines.append("")
    for lay in m["data_layers"]:
        lines.append(f"- {lay}")
    lines.append("")
    lines.append("### Layer separation")
    lines.append("")
    for s in m["layer_separation"]:
        lines.append(f"- {s}")
    lines.append("")
    lines.append("### Analytical framework")
    lines.append("")
    for f in m["analytical_framework"]:
        lines.append(f"- {f}")
    lines.append("")
    lines.append("### Pipeline steps")
    lines.append("")
    for step in m["pipeline_steps"]:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("### Integrity statements")
    lines.append("")
    for i in m["integrity_statements"]:
        lines.append(f"- {i}")
    lines.append("")

    sel = draft["case_selection"]
    lines.append("## Case selection")
    lines.append("")
    lines.append(f"- primary case: {sel['primary_case']}")
    if sel["comparators"]:
        lines.append(f"- comparators: {', '.join(sel['comparators'])}")
    lines.append("")
    lines.append("### Rationale")
    lines.append("")
    for r in sel["rationale"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("### Selection limitations")
    lines.append("")
    for lim in sel["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")

    ev = draft["evidence_description"]
    lines.append("## Evidence description")
    lines.append("")
    lines.append("Corpus state: "
                 + ", ".join(f"{k}={v}" for k, v in ev["corpus_state"].items()))
    lines.append("")
    lines.append("### Per-case coverage")
    lines.append("")
    for row in ev["per_case"]:
        dims = ", ".join(row["dimensions_with_evidence"]) or "none"
        lines.append(f"- **{row['case']}**: {row['evidence_count']} evidence "
                     f"record(s) from {row['source_count']} source(s); "
                     f"dimensions with evidence: {dims}")
    lines.append("")
    lines.append(f"### Source register ({len(ev['source_register'])})")
    lines.append("")
    for s in ev["source_register"]:
        date = s["publication_date"] or "undated"
        lines.append(f"- {s['source_id']}: {s['title']} "
                     f"[{s['source_type']}, {s['jurisdiction']}] "
                     f"({date}; {s['evidence_count']} evidence records)")
    lines.append("")

    study = draft["ethiopia_case_study"]
    lines.append(f"## Case study: {study['case']['title']}")
    lines.append("")
    cs = study["coverage_summary"]
    lines.append(f"Coverage: {', '.join(f'{k}={v}' for k, v in cs.items())}")
    lines.append("")
    for sec in study["dimension_sections"]:
        conf = f"{sec['confidence']}/5" if sec["confidence"] is not None \
            else "n/a"
        lines.append(f"### {sec['title']} — {sec['evidence_status']} "
                     f"(confidence {conf})")
        lines.append("")
        for claim in sec["narrative"]:
            tag = "[no evidence]" if not claim["evidence_ids"] else \
                "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) + "]"
            lines.append(f"- {claim['statement']} {tag} "
                         f"(_origin: {claim['statement_origin']}_)")
        lines.append("")

    comp = draft["comparative_analysis"]
    if comp["comparative_sections"]:
        lines.append("## Comparative analysis")
        lines.append("")
        for sec in comp["comparative_sections"]:
            rel = f" ({sec['support_relation']})" if sec["support_relation"] \
                else ""
            lines.append(f"### {sec['dimension']} — "
                         f"{' vs '.join(sec['pair'])}{rel}")
            lines.append("")
            for claim in sec["narrative"]:
                tag = "[no evidence]" if not claim["evidence_ids"] else \
                    "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) \
                    + "]"
                lines.append(f"- {claim['statement']} {tag}")
            lines.append("")

    xd = draft["cross_dimension_findings"]
    if xd["cross_cutting_patterns"]:
        lines.append("## Cross-dimensional findings")
        lines.append("")
        for p in xd["cross_cutting_patterns"]:
            lines.append(f"- **{p['pattern']}** ({p['scope']}): "
                         f"{p['statement']}")
        lines.append("")

    disc = draft["discussion"]
    lines.append("## Discussion")
    lines.append("")
    for point in disc["points"]:
        lines.append(f"### {point['dimension']} "
                     f"({point['evidence_status']})")
        lines.append("")
        for claim in point["claims"]:
            tag = "[no evidence]" if not claim["evidence_ids"] else \
                "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) + "]"
            lines.append(f"- {claim['statement']} {tag} "
                         f"(_origin: {claim['statement_origin']}_)")
        if point["open_questions"]:
            lines.append("")
            lines.append("Open questions:")
            for q in point["open_questions"]:
                lines.append(f"- {q}")
        lines.append("")

    gaps = draft["gaps"]
    lines.append(f"## Research gaps ({len(gaps['remaining_research_gaps'])})")
    lines.append("")
    levels = {"high": 0, "medium": 0, "low": 0}
    for g in gaps["remaining_research_gaps"]:
        levels[g["priority_level"]] = levels.get(g["priority_level"], 0) + 1
    lines.append(f"- high: {levels['high']}, medium: {levels['medium']}, "
                 f"low: {levels['low']}")
    lines.append("")
    for g in gaps["remaining_research_gaps"]:
        lines.append(f"- `{g['gap_id']}` ({g['priority_level']}, "
                     f"`{g['category']}`, dimension {g['dimension']})")
    lines.append("")
    if gaps["research_guidance"]:
        lines.append("### Research guidance")
        lines.append("")
        for item in gaps["research_guidance"]:
            lines.append(f"- `{item['gap_id']}` ({item['priority_level']}): "
                         f"{item['research_question']}")
        lines.append("")

    lim = draft["limitations"]
    lines.append(f"## Limitations ({len(lim['limitations'])})")
    lines.append("")
    for l in lim["limitations"]:
        lines.append(f"- {l}")
    lines.append("")

    concl = draft["conclusion"]
    lines.append("## Conclusion")
    lines.append("")
    for claim in concl["claims"]:
        tag = "[no evidence]" if not claim["evidence_ids"] else \
            "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) + "]"
        lines.append(f"- {claim['statement']} {tag}")
    lines.append("")
    if concl["what_is_established"]:
        lines.append("### What the corpus establishes")
        lines.append("")
        for c in concl["what_is_established"]:
            lines.append(f"- {c}")
        lines.append("")
    if concl["what_is_not_established"]:
        lines.append("### What the corpus does not establish")
        lines.append("")
        for c in concl["what_is_not_established"]:
            lines.append(f"- {c}")
        lines.append("")
    lines.append(f"_Scope notice: {concl['scope_notice']}_")
    lines.append("")

    lines.append(f"## Traceability appendix ({len(draft['traceability'])} rows)")
    lines.append("")
    for row in draft["traceability"]:
        lines.append(f"- ev{row['evidence_id']} -> {row['section_id']} "
                     f"(source {row['source_id']})")
    lines.append("")
    return "\n".join(lines)