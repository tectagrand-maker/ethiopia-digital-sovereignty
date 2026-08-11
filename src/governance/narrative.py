"""Step 12: Evidence-Traceable Case-Study Narrative.

Turns the Step 8 case-study dossier, the Step 11 findings synthesis and the
Step 9 research-gap inventory into a **draft case-study narrative** whose every
claim is traceable to an evidence id. The narrative is generated
deterministically from the committed evidence database; nothing is invented.

Research-integrity rules preserved from the project's evidence policy:

- Every narrative claim carries the evidence ids that back it. A statement with
  no evidence is explicitly marked ``corpus_limitation`` (a statement about the
  corpus, never a negative assessment of the jurisdiction).
- Evidence claims are rendered from the recorded claim text, interpretations
  from governance-observation assessments, and opening/limitation statements
  from the Step 11 findings layer. None of these layers is silently merged.
- ``missing_evidence`` is never converted into a negative verdict.
- No numeric governance scores, indices or rankings are produced.
- The narrative is a pure function of the committed database: identical state
  produces byte-identical JSON and Markdown. No timestamps are emitted.

The output is a *draft* narrative layer — not the final academic paper. It
keeps every sentence anchored to ``evidence_id`` so that the final writing
process can compose prose without losing traceability.
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, field_validator, model_validator

from src.evidence.models import GOVERNANCE_DIMENSIONS, Evidence
from src.governance.casestudy import case_study_dossier
from src.governance.comparison import (
    _cell_observations, ConflictRef,
)
from src.governance.findings import (
    STATEMENT_ORIGINS, _jurlabel, build_findings_report,
)
from src.governance.matrix import (
    _jurisdiction_evidence_ids,
    SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS,
)
from src.governance.research_gaps import (
    discover_gaps, CROSS_CASE_LABEL, RECOMMENDED_SOURCE_TYPES,
    RESEARCH_QUESTION_TEMPLATES,
)

NARRATIVE_TYPE = "case_study_narrative"
SCHEMA_VERSION = 1

VALID_STATUSES = {SUPPORTED_STATUS, PARTIAL_STATUS, MISSING_STATUS, "conflicting"}

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


# ---------------------------------------------------------------------------
# Output schema (integrity constraints)
# ---------------------------------------------------------------------------

class NarrativeClaim(BaseModel):
    """One traceable sentence of the narrative with its evidence anchors."""
    claim_id: str
    statement: str
    statement_origin: str
    evidence_ids: List[int] = []

    @field_validator('statement_origin')
    @classmethod
    def _check_origin(cls, v):
        if v not in STATEMENT_ORIGINS:
            raise ValueError(f"Invalid statement_origin: {v!r}")
        return v

    @field_validator('statement')
    @classmethod
    def _check_statement(cls, v):
        if not v or not v.strip():
            raise ValueError("Narrative statement must not be empty")
        return v


class NarrativeGapRef(BaseModel):
    """Reference to a Step 9 research gap touching the section (never a
    duplicated definition)."""
    gap_id: str
    category: str
    scope: str
    dimension: str
    evidence_status: str
    priority_level: str


class NarrativeSection(BaseModel):
    """One governance-dimension section of the narrative."""
    section_id: str
    title: str
    dimension: str
    evidence_status: str
    evidence_count: int
    source_count: int
    observation_count: int
    confidence: Optional[int] = None
    narrative: List[NarrativeClaim]
    research_gap_refs: List[NarrativeGapRef] = []

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


class ComparativeSection(BaseModel):
    """A cross-case narrative block. Only produced for evidenced pairs; absent
    coverage is reported as an explicit limitation, never as a verdict."""
    section_id: str
    dimension: str
    pair: List[str]
    support_relation: str = ""
    narrative: List[NarrativeClaim]

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @model_validator(mode='after')
    def _pair_valid(self):
        if len(self.pair) != 2 or len(set(self.pair)) != 2:
            raise ValueError("Comparative narrative requires exactly 2 distinct cases.")
        return self


class CrossCuttingPattern(BaseModel):
    """A cross-dimension pattern (never a causal claim)."""
    pattern: str
    scope: str
    statement: str
    evidence_ids: List[int] = []
    dimensions: List[str] = []

    @field_validator('dimensions')
    @classmethod
    def _check_dimensions(cls, v):
        for d in v:
            if d not in GOVERNANCE_DIMENSIONS:
                raise ValueError(f"Invalid governance dimension: {d!r}")
        return v


class SynthesisBlock(BaseModel):
    major_supported_findings: List[NarrativeClaim] = []
    partial_findings: List[NarrativeClaim] = []
    conflicting_evidence: List[ConflictRef] = []
    missing_evidence_areas: List[str] = []
    cross_dimension_patterns: List[str] = []
    limitations: List[str] = []


class ResearchGuidance(BaseModel):
    """One prioritized research action surfaced as guidance (never a verdict)."""
    gap_id: str
    category: str
    scope: str
    dimension: str
    priority_level: str
    research_question: str

    @field_validator('dimension')
    @classmethod
    def _check_dimension(cls, v):
        if v not in GOVERNANCE_DIMENSIONS:
            raise ValueError(f"Invalid governance dimension: {v!r}")
        return v

    @field_validator('research_question')
    @classmethod
    def _must_be_question(cls, v):
        if not v.endswith("?"):
            raise ValueError("research_question must be phrased as a question")
        return v


class TraceabilityRow(BaseModel):
    """One evidence anchor used somewhere in the narrative."""
    evidence_id: int
    section_id: str
    dimension: str
    source_id: int = 0
    claim: str = ""


class CaseNarrative(BaseModel):
    narrative_type: str = NARRATIVE_TYPE
    schema_version: int = SCHEMA_VERSION
    note: str
    case: dict
    coverage_summary: Dict[str, int]
    dimension_sections: List[NarrativeSection]
    comparative_sections: List[ComparativeSection] = []
    cross_cutting_patterns: List[CrossCuttingPattern] = []
    synthesis: SynthesisBlock
    research_guidance: List[ResearchGuidance] = []
    traceability: List[TraceabilityRow] = []
    limitations: List[str] = []

    @field_validator('dimension_sections')
    @classmethod
    def _cover_all_dimensions(cls, v):
        ids = [sec.dimension for sec in v]
        if sorted(ids) != sorted(GOVERNANCE_DIMENSIONS):
            raise ValueError(
                "Narrative must contain exactly the 12 governance dimensions.")
        if [sec.dimension for sec in v] != list(GOVERNANCE_DIMENSIONS):
            raise ValueError(
                "Narrative dimension sections must follow the fixed dimension order.")
        return v


# ---------------------------------------------------------------------------
# Dimension section construction
# ---------------------------------------------------------------------------

def _display_title(dimension):
    return dimension.replace('_', ' ').title()


def _section_claims(jurisdiction, dimension, profile, cell_finding):
    """Deterministic ordered list of claims for one dimension section."""
    jl = _jurlabel(jurisdiction)
    claims = []
    seq = 0

    def _next_claim():
        nonlocal seq
        seq += 1
        return f"{jl}-{dimension}-claim-{seq:02d}"

    # Opening statement from the Step 11 per-cell finding (traceable).
    opening = cell_finding
    claims.append({
        "claim_id": _next_claim(),
        "statement": opening["statement"],
        "statement_origin": opening["statement_origin"],
        "evidence_ids": sorted(
            r["evidence_id"] for r in opening["evidence_refs"]),
    })

    # Evidence claims: verbatim claim text from the recorded corpus.
    for trace in profile["evidence"]:
        claims.append({
            "claim_id": _next_claim(),
            "statement": trace["claim"],
            "statement_origin": "evidence_derived",
            "evidence_ids": [trace["evidence_id"]],
        })

    # Interpretation claims: assessments from linked governance observations.
    for obs in _cell_observations(jurisdiction, dimension):
        if not obs.assessment:
            continue
        eids = sorted(
            eo.evidence.evidence_id for eo in obs.evidence_links)
        claims.append({
            "claim_id": _next_claim(),
            "statement": obs.assessment,
            "statement_origin": "analytical_interpretation",
            "evidence_ids": eids,
        })

    # Limitation claims from the findings layer (corpus statements).
    for limitation in opening["limitations"]:
        claims.append({
            "claim_id": _next_claim(),
            "statement": limitation,
            "statement_origin": "corpus_limitation",
            "evidence_ids": [],
        })

    return claims


def _narrative_section(jurisdiction, dimension, profile, cell_finding):
    claims = _section_claims(jurisdiction, dimension, profile, cell_finding)
    return {
        "section_id": f"{_jurlabel(jurisdiction)}-{dimension}",
        "title": _display_title(dimension),
        "dimension": dimension,
        "evidence_status": profile["evidence_status"],
        "evidence_count": profile["evidence_count"],
        "source_count": profile["source_count"],
        "observation_count": profile["observation_count"],
        "confidence": profile["confidence"],
        "narrative": claims,
        "research_gap_refs": cell_finding["research_gap_refs"],
    }


# ---------------------------------------------------------------------------
# Comparative, cross-cutting, synthesis, guidance
# ---------------------------------------------------------------------------

def _comparative_sections(jurisdiction, comparative_findings):
    sections = []
    for i, f in enumerate(comparative_findings):
        claims = [{
            "claim_id": f"{_jurlabel(jurisdiction)}-{f['dimension']}-"
                        f"comparative-{i + 1:02d}",
            "statement": f["statement"],
            "statement_origin": f["statement_origin"],
            "evidence_ids": sorted(
                r["evidence_id"] for r in f["evidence_refs"]),
        }]
        claims.extend({
            "claim_id": f"{_jurlabel(jurisdiction)}-{f['dimension']}-"
                        f"comparative-{i + 1:02d}-lim",
            "statement": limitation,
            "statement_origin": "corpus_limitation",
            "evidence_ids": [],
        } for limitation in f["limitations"])
        sections.append({
            "section_id": f"{_jurlabel(jurisdiction)}-{f['dimension']}-"
                          f"comparative-{i + 1:02d}",
            "dimension": f["dimension"],
            "pair": list(f["pair"]),
            "support_relation": f.get("support_relation", ""),
            "narrative": claims,
        })
    return sections


def _cross_cutting_patterns(cross_dimension_findings, jurisdiction):
    patterns = []
    for f in cross_dimension_findings:
        if f["scope"] not in (jurisdiction, "all_cases"):
            continue
        patterns.append({
            "pattern": f["pattern"],
            "scope": f["scope"],
            "statement": f["statement"],
            "evidence_ids": sorted(f["evidence_ids"]),
            "dimensions": list(f["dimensions"]),
        })
    return patterns


def _synthesis_block(jurisdiction, dossier, report):
    jl = _jurlabel(jurisdiction)
    syn = dossier["synthesis"]

    def _claims(entries, prefix):
        return [{
            "claim_id": f"{jl}-synthesis-{prefix}-{i + 1:02d}",
            "statement": entry["claim"],
            "statement_origin": "evidence_derived",
            "evidence_ids": sorted(entry["evidence_ids"]),
        } for i, entry in enumerate(entries)]

    return {
        "major_supported_findings": _claims(
            syn["major_supported_findings"], "major"),
        "partial_findings": _claims(syn["partial_findings"], "partial"),
        "conflicting_evidence": list(syn["conflicting_evidence"]),
        "missing_evidence_areas": list(syn["missing_evidence_areas"]),
        "cross_dimension_patterns": list(syn["cross_dimension_patterns"]),
        "limitations": list(syn["limitations"]),
    }


def _research_guidance(jurisdiction, gaps=None):
    if gaps is None:
        gaps = discover_gaps()
    gaps = [
        g for g in gaps
        if g["jurisdiction"] == jurisdiction
        or jurisdiction in g["affected_cases"]
    ]
    gaps.sort(key=lambda g: (
        _PRIORITY_RANK.get(g["priority_level"], 3), g["gap_id"]))

    guidance = []
    for g in gaps:
        sources = ", ".join(
            sorted(RECOMMENDED_SOURCE_TYPES.get(g["category"], [])))
        question = RESEARCH_QUESTION_TEMPLATES[g["category"]].format(
            jurisdiction=g["jurisdiction"], dimension=g["dimension"],
            sources=sources)
        guidance.append({
            "gap_id": g["gap_id"],
            "category": g["category"],
            "scope": g["scope"],
            "dimension": g["dimension"],
            "priority_level": g["priority_level"],
            "research_question": question,
        })
    return guidance


# ---------------------------------------------------------------------------
# Traceability manifest
# ---------------------------------------------------------------------------

def _evidence_claim_text(eid):
    e = Evidence.get_or_none(Evidence.evidence_id == eid)
    return e.claim if e else ""


def _traceability(sections, comparative_sections, patterns):
    rows = []
    for sec in sections:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                rows.append({
                    "evidence_id": eid,
                    "section_id": sec["section_id"],
                    "dimension": sec["dimension"],
                    "source_id": (Evidence.get_by_id(eid).source.source_id
                                  if Evidence.get_or_none(
                                      Evidence.evidence_id == eid) else 0),
                    "claim": _evidence_claim_text(eid),
                })
    for sec in comparative_sections:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                rows.append({
                    "evidence_id": eid,
                    "section_id": sec["section_id"],
                    "dimension": sec["dimension"],
                    "source_id": (Evidence.get_by_id(eid).source.source_id
                                  if Evidence.get_or_none(
                                      Evidence.evidence_id == eid) else 0),
                    "claim": _evidence_claim_text(eid),
                })
    for p in patterns:
        for eid in p["evidence_ids"]:
            rows.append({
                "evidence_id": eid,
                "section_id": f"cross-cutting:{p['pattern']}",
                "dimension": ";".join(p["dimensions"]) or p["scope"],
                "source_id": (Evidence.get_by_id(eid).source.source_id
                              if Evidence.get_or_none(
                                  Evidence.evidence_id == eid) else 0),
                "claim": _evidence_claim_text(eid),
            })
    # deterministic order, deduplicated on (evidence, section) so the manifest
    # records anchor pairs, not repeated claims over the same evidence.
    rows.sort(key=lambda r: (r["evidence_id"], r["section_id"]))
    seen = set()
    out = []
    for r in rows:
        key = (r["evidence_id"], r["section_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Narrative assembly
# ---------------------------------------------------------------------------

_LIMITATIONS = [
    "This narrative draft is generated deterministically from the current "
    "evidence corpus; it is not the final academic paper.",
    "Every claim is traceable to its evidence references; statements without "
    "evidence are explicitly marked as corpus limitations, never as verdicts.",
    "missing_evidence reflects corpus coverage, not a negative assessment "
    "(absence of evidence is not evidence of absence).",
    "No numeric governance scores, indices or rankings are produced.",
    "Comparative narrative blocks compare recorded evidence coverage; they are "
    "not scores or rankings.",
    "Cross-cutting patterns describe the distribution of evidence and record "
    "nothing about causation.",
    "The narrative is reproducible only while the committed manifests and "
    "database state remain unchanged.",
]


def case_study_narrative(jurisdiction, comparators=None):
    """Deterministic, evidence-traceable narrative draft for a jurisdiction."""
    dossier = case_study_dossier(jurisdiction, comparators)
    report = build_findings_report(case=jurisdiction)
    gaps = discover_gaps()

    profiles = {p["dimension"]: p for p in dossier["dimension_profiles"]}
    findings_by_dim = {f["dimension"]: f for f in report["findings"]}

    sections = [
        _narrative_section(
            jurisdiction, dimension, profiles[dimension],
            findings_by_dim[dimension])
        for dimension in GOVERNANCE_DIMENSIONS
    ]
    comparative_sections = _comparative_sections(
        jurisdiction, report["comparative_findings"])
    patterns = _cross_cutting_patterns(
        report["cross_dimension_findings"], jurisdiction)

    return {
        "narrative_type": NARRATIVE_TYPE,
        "schema_version": SCHEMA_VERSION,
        "note": (
            "Evidence-traceable case-study narrative draft. Every claim is "
            "anchored to evidence ids; statements with no evidence are explicit "
            "corpus limitations. This is not a score, ranking, or the final "
            "academic paper."
        ),
        "case": dossier["case"],
        "coverage_summary": dossier["case"]["coverage_summary"],
        "dimension_sections": sections,
        "comparative_sections": comparative_sections,
        "cross_cutting_patterns": patterns,
        "synthesis": _synthesis_block(jurisdiction, dossier, report),
        "research_guidance": _research_guidance(jurisdiction, gaps),
        "traceability": _traceability(sections, comparative_sections, patterns),
        "limitations": list(_LIMITATIONS),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_narrative(narrative):
    """Validate a narrative draft against the schema and the committed database.

    Raises pydantic.ValidationError on schema violations and ValueError on
    database-integrity violations. Returns the parsed model on success.
    """
    model = CaseNarrative(**narrative)

    jurisdiction = narrative["case"]["jurisdiction"]
    live = {g["gap_id"]: g for g in discover_gaps()}

    # --- dimension sections ---
    section_ids = []
    all_evidence_ids = set()
    for sec in narrative["dimension_sections"]:
        section_ids.append(sec["section_id"])
        allowed = _jurisdiction_evidence_ids(jurisdiction, sec["dimension"])
        claim_ids = []
        for claim in sec["narrative"]:
            claim_ids.append(claim["claim_id"])
            for eid in claim["evidence_ids"]:
                all_evidence_ids.add(eid)
                if eid not in allowed:
                    raise ValueError(
                        f"Narrative section {sec['section_id']}: evidence {eid} "
                        f"does not belong to the cell "
                        f"{jurisdiction}|{sec['dimension']}.")
            if claim["statement_origin"] != "corpus_limitation" \
                    and not claim["evidence_ids"]:
                raise ValueError(
                    f"Claim {claim['claim_id']} has no evidence references but "
                    "is not a corpus-limitation statement.")
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError(
                f"Duplicate claim identifiers in section {sec['section_id']}.")
        for ref in sec["research_gap_refs"]:
            _validate_gap_ref(ref, jurisdiction, sec["dimension"], live)
    if len(section_ids) != len(set(section_ids)):
        raise ValueError("Duplicate narrative section identifiers.")

    # --- comparative sections ---
    cids = []
    for sec in narrative["comparative_sections"]:
        cids.append(sec["section_id"])
        for claim in sec["narrative"]:
            all_evidence_ids.update(claim["evidence_ids"])
    if len(cids) != len(set(cids)):
        raise ValueError("Duplicate comparative section identifiers.")

    # --- cross-cutting patterns ---
    for p in narrative["cross_cutting_patterns"]:
        all_evidence_ids.update(p["evidence_ids"])

    # --- all referenced evidence ids must exist ---
    for eid in sorted(all_evidence_ids):
        if not Evidence.get_or_none(Evidence.evidence_id == eid):
            raise ValueError(f"Orphan evidence reference: {eid}")

    # --- synthesis claims must be evidenced ---
    for claim in (narrative["synthesis"]["major_supported_findings"]
                  + narrative["synthesis"]["partial_findings"]):
        for eid in claim["evidence_ids"]:
            if not Evidence.get_or_none(Evidence.evidence_id == eid):
                raise ValueError(
                    f"Synthesis claim {claim['claim_id']}: orphan evidence {eid}.")

    # --- research guidance resolves against the live gap inventory ---
    for item in narrative["research_guidance"]:
        g = live.get(item["gap_id"])
        if not g:
            raise ValueError(
                f"Research guidance {item['gap_id']} is not in discover_gaps().")
        if jurisdiction not in (g["jurisdiction"], *g["affected_cases"]):
            raise ValueError(
                f"Research guidance {item['gap_id']} does not touch "
                f"{jurisdiction}.")

    # --- traceability manifest ---
    referenced = {}
    for sec in narrative["dimension_sections"]:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                referenced.setdefault(eid, set()).add(sec["section_id"])
    for sec in narrative["comparative_sections"]:
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                referenced.setdefault(eid, set()).add(sec["section_id"])
    for p in narrative["cross_cutting_patterns"]:
        for eid in p["evidence_ids"]:
            referenced.setdefault(eid, set()).add(
                f"cross-cutting:{p['pattern']}")

    rows = narrative["traceability"]
    row_ids = [(r["evidence_id"], r["section_id"]) for r in rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("Duplicate traceability rows.")
    manifest = {(r["evidence_id"], r["section_id"]) for r in rows}
    if set(referenced) != {r["evidence_id"] for r in rows}:
        raise ValueError("Traceability manifest evidence set does not match "
                         "the evidence actually referenced in the narrative.")
    for r in rows:
        if r["section_id"] not in referenced.get(r["evidence_id"], set()):
            raise ValueError(
                f"Traceability manifests an unreferenced pair: ev"
                f"{r['evidence_id']} -> {r['section_id']}.")

    return model


def _validate_gap_ref(ref, jurisdiction, dimension, live):
    g = live.get(ref["gap_id"])
    if not g:
        raise ValueError(
            f"Research-gap reference {ref['gap_id']} is not in discover_gaps().")
    if g["jurisdiction"] != jurisdiction or g["dimension"] != dimension:
        raise ValueError(
            f"Gap reference {ref['gap_id']} is not a cell gap for "
            f"{jurisdiction}|{dimension}.")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def narrative_to_json(narrative):
    return json.dumps(narrative, indent=2, ensure_ascii=False)


def narrative_to_markdown(narrative):
    """Deterministic human-readable rendering with inline evidence citations."""
    lines = []
    case = narrative["case"]
    lines.append(f"# Case-Study Narrative Draft: {case['title']}")
    lines.append("")
    lines.append(narrative["note"])
    lines.append("")

    cs = narrative["coverage_summary"]
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- jurisdiction: `{case['jurisdiction']}`")
    lines.append(f"- evidence corpus: {case['evidence_count']} evidence "
                 f"records from {case['source_count']} sources")
    lines.append(f"- status counts: {', '.join(f'{k}={v}' for k, v in cs.items())}")
    lines.append("")

    for sec in narrative["dimension_sections"]:
        conf = f"{sec['confidence']}/5" if sec["confidence"] is not None else "n/a"
        lines.append(f"## {sec['title']} — {sec['evidence_status']} "
                     f"(confidence {conf})")
        lines.append("")
        for claim in sec["narrative"]:
            tag = "[no evidence]" if not claim["evidence_ids"] else \
                "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) + "]"
            lines.append(f"- {claim['statement']} {tag} "
                         f"(_origin: {claim['statement_origin']}_)")
        if sec["research_gap_refs"]:
            lines.append("")
            lines.append("Linked research gaps: "
                         + "; ".join(r["gap_id"] for r in sec["research_gap_refs"]))
        lines.append("")

    if narrative["comparative_sections"]:
        lines.append("## Comparative context")
        lines.append("")
        for sec in narrative["comparative_sections"]:
            rel = f" ({sec['support_relation']})" if sec["support_relation"] else ""
            lines.append(f"### {sec['dimension']} — "
                         f"{' vs '.join(sec['pair'])}{rel}")
            lines.append("")
            for claim in sec["narrative"]:
                tag = "[no evidence]" if not claim["evidence_ids"] else \
                    "[ev " + ", ".join(str(i) for i in claim["evidence_ids"]) + "]"
                lines.append(f"- {claim['statement']} {tag}")
            lines.append("")

    if narrative["cross_cutting_patterns"]:
        lines.append("## Cross-cutting patterns")
        lines.append("")
        for p in narrative["cross_cutting_patterns"]:
            lines.append(f"- **{p['pattern']}** ({p['scope']}): {p['statement']}")
        lines.append("")

    syn = narrative["synthesis"]
    lines.append("## Synthesis")
    lines.append("")
    if syn["major_supported_findings"]:
        lines.append("### Major supported findings")
        for c in syn["major_supported_findings"]:
            lines.append(f"- {c['statement']} [ev "
                         + ", ".join(str(i) for i in c["evidence_ids"]) + "]")
        lines.append("")
    if syn["partial_findings"]:
        lines.append("### Partial findings")
        for c in syn["partial_findings"]:
            lines.append(f"- {c['statement']} [ev "
                         + ", ".join(str(i) for i in c["evidence_ids"]) + "]")
        lines.append("")
    if syn["conflicting_evidence"]:
        lines.append("### Recorded conflicts")
        for c in syn["conflicting_evidence"]:
            lines.append(f"- ev{c['evidence_a']} vs ev{c['evidence_b']}")
        lines.append("")
    lines.append(f"### Missing-evidence areas: "
                 + (", ".join(syn["missing_evidence_areas"]) or "none"))
    lines.append("")
    lines.append("### Cross-dimension patterns")
    for p in syn["cross_dimension_patterns"]:
        lines.append(f"- {p}")
    lines.append("")

    if narrative["research_guidance"]:
        lines.append("## Research guidance (Step 9)")
        lines.append("")
        for item in narrative["research_guidance"]:
            lines.append(f"- `{item['gap_id']}` ({item['priority_level']}): "
                         f"{item['research_question']}")
        lines.append("")

    lines.append("## Limitations")
    lines.append("")
    for limitation in narrative["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")

    lines.append(f"## Traceability manifest "
                 f"({len(narrative['traceability'])} rows)")
    lines.append("")
    for row in narrative["traceability"]:
        lines.append(f"- ev{row['evidence_id']} -> {row['section_id']} "
                     f"(source {row['source_id']})")
    lines.append("")
    return "\n".join(lines)