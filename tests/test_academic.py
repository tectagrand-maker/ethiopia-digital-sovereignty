r"""Step 13: Evidence-Backed Academic Research Draft.

Verifies the reproducible academic research-draft layer built on the Step 6-12
artifacts (corpus, baseline, dossier, gaps, findings, narrative). Covers:

- deterministic, machine-readable academic draft derived only from the database
- the required notice: it is an evidence-backed research draft, not validated
  scholarly truth or a final publication
- section completeness (title, abstract, problem, methodology, framework,
  case selection, evidence description, case study, comparative, cross-cutting,
  discussion, limitations, gaps, conclusion, source register, traceability)
- 12 dimension sections in the fixed governance-dimension order
- every substantive claim carries evidence references (or is a corpus
  limitation) with a controlled statement_origin
- no fabricated sources/statistics; the source register mirrors the database
- no banning: missing_evidence never a negative verdict, no scores/rankings,
  no causal claims
- a traceability appendix that exactly matches the referenced evidence
- full integrity validation against schema and database
"""

import copy
import json
import os

import pytest
from pydantic import ValidationError

from src.evidence.collection import import_source_manifest
from src.evidence.ingestion import import_from_json
from src.evidence.models import (
    Evidence, Source, GOVERNANCE_DIMENSIONS,
)
from src.governance.analysis import create_observation
from src.governance.academic import (
    build_academic_draft, validate_academic_draft,
    academic_to_json, academic_to_markdown,
    ACADEMIC_TYPE, SCHEMA_VERSION, DRAFT_NOTICE,
)
from src.governance.findings import STATEMENT_ORIGINS

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@pytest.fixture()
def committed_db(eds_test_db):
    """Load the committed manifests into the isolated test DB (mirrors
    scripts/rebuild_db.py but bound to the temporary database)."""
    import_source_manifest(os.path.join(DATA, "sources", "catalog.json"))
    with open(os.path.join(DATA, "evidence", "corpus_manifest.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    for entry in manifest:
        import_from_json(os.path.join(DATA, "evidence", entry["file"]),
                         entry["source_id"])
    with open(os.path.join(DATA, "evidence", "observations_manifest.json"),
              encoding="utf-8") as f:
        obs_manifest = json.load(f)
    for entry in obs_manifest:
        create_observation(entry["observation"], entry["evidence_ids"])
    return eds_test_db


@pytest.fixture()
def draft(committed_db):
    return build_academic_draft("Ethiopia")


# ---------------------------------------------------------------------------
# Shape, determinism, notice
# ---------------------------------------------------------------------------

def test_academic_draft_shape(draft):
    assert draft["academic_type"] == ACADEMIC_TYPE
    assert draft["schema_version"] == SCHEMA_VERSION
    assert draft["title"].startswith("Research Draft:")
    assert draft["note"]
    assert draft["ethiopia_case_study"]["case"]["jurisdiction"] == "Ethiopia"


def test_academic_draft_carries_notice(draft):
    assert DRAFT_NOTICE in draft["note"]
    assert "not automatically validated scholarly truth" in \
        draft["abstract"]["scope_statement"]
    assert "not automatically validated scholarly truth" in \
        draft["conclusion"]["scope_notice"]


def test_academic_draft_all_sections_present(draft):
    for key in ("abstract", "research_problem", "methodology",
                "case_selection", "evidence_description", "ethiopia_case_study",
                "comparative_analysis", "cross_dimension_findings",
                "discussion", "limitations", "gaps", "conclusion",
                "traceability"):
        assert key in draft, f"missing section: {key}"


def test_academic_draft_deterministic(draft):
    d2 = build_academic_draft("Ethiopia")
    assert academic_to_json(draft) == academic_to_json(d2)


def test_academic_draft_no_timestamp_fields(draft):
    assert not (set(draft.keys()) & {"timestamp", "generated_at", "run_at"})


# ---------------------------------------------------------------------------
# Research problem / questions / objectives
# ---------------------------------------------------------------------------

def test_research_problem_non_empty(draft):
    assert draft["research_problem"]["research_problem"]
    assert draft["research_problem"]["objectives"]


def test_research_questions_phrase_as_questions(draft):
    qs = draft["research_problem"]["research_questions"]
    assert qs
    for q in qs:
        assert q["question"].endswith("?")
        assert q["source"] in {"central_question", "research_guidance"}
    assert any(q["source"] == "central_question" for q in qs)


# ---------------------------------------------------------------------------
# Methodology / framework / case selection
# ---------------------------------------------------------------------------

def test_methodology_integrity_block(draft):
    m = draft["methodology"]
    assert m["approach"]
    assert m["confidence_rule"]
    assert m["determinism"]
    joined = " ".join(m["integrity_statements"]).lower()
    assert "fabricated" in joined
    assert "missing_evidence" in joined


def test_case_selection_primary_case(draft):
    sel = draft["case_selection"]
    assert sel["primary_case"] == "Ethiopia"
    assert "Kenya" in sel["comparators"]
    assert "European Union" in sel["comparators"]
    assert any("primary case" in r for r in sel["rationale"])
    # incomplete case-selection rationale must be marked as a limitation
    assert sel["limitations"]


def test_case_selection_limits_are_corpus_based(draft):
    joined = " ".join(draft["case_selection"]["limitations"]).lower()
    assert "corpus" in joined or "coverage" in joined


# ---------------------------------------------------------------------------
# Evidence description & source register
# ---------------------------------------------------------------------------

def test_evidence_description_counts(draft):
    ev = draft["evidence_description"]
    cs = ev["corpus_state"]
    real = [e for e in Evidence.select() if e.data_status == 'real']
    assert cs["evidence"] == len(real)
    assert len(ev["per_case"]) >= 3  # Ethiopia, Kenya, EU


def test_source_register_no_fabrication(draft):
    register = draft["evidence_description"]["source_register"]
    assert register
    db_ids = {s.source_id for s in Source.select()}
    for entry in register:
        assert entry["source_id"] in db_ids
        assert entry["title"]
        # every register count matches the database
        count = sum(1 for e in Evidence.select()
                    if e.source.source_id == entry["source_id"]
                    and e.data_status == 'real')
        assert entry["evidence_count"] == count
    ids = [e["source_id"] for e in register]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Case-study chapter
# ---------------------------------------------------------------------------

def test_case_study_has_all_12_dimensions(draft):
    dims = [s["dimension"]
            for s in draft["ethiopia_case_study"]["dimension_sections"]]
    assert dims == list(GOVERNANCE_DIMENSIONS)


def test_case_study_claims_controlled_origins(draft):
    for sec in draft["ethiopia_case_study"]["dimension_sections"]:
        for claim in sec["narrative"]:
            assert claim["statement_origin"] in STATEMENT_ORIGINS


def test_case_study_claims_traceable(draft):
    for sec in draft["ethiopia_case_study"]["dimension_sections"]:
        for claim in sec["narrative"]:
            if claim["statement_origin"] == "evidence_derived":
                assert claim["evidence_ids"]
            for eid in claim["evidence_ids"]:
                assert Evidence.get_or_none(Evidence.evidence_id == eid)


def test_case_study_missing_cell_is_limitation(draft):
    by_dim = {s["dimension"]: s
              for s in draft["ethiopia_case_study"]["dimension_sections"]}
    missing = [d for d, s in by_dim.items()
               if s["evidence_status"] == "missing_evidence"]
    assert missing  # Ethiopia private_sector_dependence has no evidence
    for dim in missing:
        claims = by_dim[dim]["narrative"]
        assert any(c["statement_origin"] == "corpus_limitation"
                   for c in claims)
        joined = " ".join(c["statement"].lower() for c in claims)
        assert "not evidence of absence" in joined or \
            "never a negative" in joined


# ---------------------------------------------------------------------------
# Comparative / cross-cutting
# ---------------------------------------------------------------------------

def test_comparative_sections_pairwise(draft):
    sections = draft["comparative_analysis"]["comparative_sections"]
    assert sections
    for sec in sections:
        assert len(sec["pair"]) == 2
        assert "Ethiopia" in sec["pair"]


def test_cross_cutting_never_causal(draft):
    for p in draft["cross_dimension_findings"]["cross_cutting_patterns"]:
        if p["pattern"] == "shared_source_pattern":
            assert "not a causal link" in p["statement"]
        if p["pattern"] == "no_causal_inference":
            assert "does not" in p["statement"]


# ---------------------------------------------------------------------------
# Discussion
# ---------------------------------------------------------------------------

def test_discussion_covers_all_dimensions(draft):
    dims = [p["dimension"] for p in draft["discussion"]["points"]]
    assert dims == list(GOVERNANCE_DIMENSIONS)


def test_discussion_no_scores_or_rankings(draft):
    for point in draft["discussion"]["points"]:
        for claim in point["claims"]:
            assert not any(p in claim["statement"].lower()
                           for p in ("scored", "ranked", "score of"))


def test_discussion_open_questions_resolve(draft):
    live = {g["gap_id"] for g in _discover()}
    for point in draft["discussion"]["points"]:
        for q in point["open_questions"]:
            assert q.endswith("?")


# ---------------------------------------------------------------------------
# Conclusion / limitations / gaps
# ---------------------------------------------------------------------------

def test_conclusion_established_and_not(draft):
    concl = draft["conclusion"]
    assert DRAFT_NOTICE in concl["scope_notice"]
    asserts = " ".join(concl["what_is_established"]).lower()
    assert "supported" in asserts
    missing = " ".join(concl["what_is_not_established"]).lower()
    assert "missing coverage is not a negative" in missing or \
        "not a negative assessment" in missing


def test_gaps_resolve_against_inventory(draft):
    live = {g["gap_id"] for g in _discover()}
    assert draft["gaps"]["remaining_research_gaps"]
    for gap in draft["gaps"]["remaining_research_gaps"]:
        assert gap["gap_id"] in live
    for item in draft["gaps"]["research_guidance"]:
        assert item["gap_id"] in live
        assert item["research_question"].endswith("?")


def test_limitations_include_draft_notice(draft):
    joined = " ".join(draft["limitations"]["limitations"])
    assert "not automatically validated scholarly truth" in joined


# ---------------------------------------------------------------------------
# Traceability appendix
# ---------------------------------------------------------------------------

def test_traceability_matches_references(draft):
    referenced = set()
    referenced.update(draft["abstract"]["evidence_ids"])
    for sec in draft["ethiopia_case_study"]["dimension_sections"]:
        for claim in sec["narrative"]:
            referenced.update(claim["evidence_ids"])
    for sec in draft["comparative_analysis"]["comparative_sections"]:
        for claim in sec["narrative"]:
            referenced.update(claim["evidence_ids"])
    for p in draft["cross_dimension_findings"]["cross_cutting_patterns"]:
        referenced.update(p["evidence_ids"])
    for point in draft["discussion"]["points"]:
        for claim in point["claims"]:
            referenced.update(claim["evidence_ids"])
    for claim in draft["conclusion"]["claims"]:
        referenced.update(claim["evidence_ids"])
    manifest = {r["evidence_id"] for r in draft["traceability"]}
    assert manifest == referenced


def test_traceability_rows_unique(draft):
    rows = [(r["evidence_id"], r["section_id"])
            for r in draft["traceability"]]
    assert len(rows) == len(set(rows))


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def test_markdown_deterministic(draft):
    md1 = academic_to_markdown(draft)
    md2 = academic_to_markdown(build_academic_draft("Ethiopia"))
    assert md1 == md2
    for heading in ("# Research Draft", "## Abstract", "## Methodology",
                    "## Case selection", "## Evidence description",
                    "## Case study", "## Comparative analysis",
                    "## Cross-dimensional findings", "## Discussion",
                    "## Research gaps", "## Limitations",
                    "## Conclusion", "## Traceability appendix"):
        assert heading in md1


def test_markdown_renders_notice(draft):
    md = academic_to_markdown(draft)
    assert "not automatically validated scholarly truth" in md


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validation_passes(draft):
    model = validate_academic_draft(draft)
    assert model.academic_type == ACADEMIC_TYPE


def test_validation_rejects_bad_origin(draft):
    bad = copy.deepcopy(draft)
    bad["ethiopia_case_study"]["dimension_sections"][0]["narrative"][0][
        "statement_origin"] = "invented"
    with pytest.raises(ValidationError):
        validate_academic_draft(bad)


def test_validation_rejects_bad_dimension(draft):
    bad = copy.deepcopy(draft)
    bad["discussion"]["points"][0]["dimension"] = "not_a_dimension"
    with pytest.raises(ValidationError):
        validate_academic_draft(bad)


def test_validation_rejects_orphan_evidence(draft):
    from src.governance.academic import _real_evidence_ids
    orphan = max(_real_evidence_ids()) + 9999
    bad = copy.deepcopy(draft)
    bad["ethiopia_case_study"]["dimension_sections"][0]["narrative"][1][
        "evidence_ids"] = [orphan]
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


def test_validation_rejects_cross_cell_evidence(draft):
    bad = copy.deepcopy(draft)
    # find a Kenya-evidence id and inject it into the Ethiopia case-study cell
    kenya_ids = sorted(e.evidence_id for e in Evidence.select()
                       if e.country_or_jurisdiction == "Kenya"
                       and e.data_status == 'real')
    eth_id = draft["ethiopia_case_study"]["dimension_sections"][0][
        "narrative"][0]["evidence_ids"][0]
    other = [k for k in kenya_ids if k != eth_id]
    assert other
    bad["ethiopia_case_study"]["dimension_sections"][0]["narrative"][0][
        "evidence_ids"] = [other[0]]
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


def test_validation_rejects_unsupported_claim(draft):
    bad = copy.deepcopy(draft)
    bad["ethiopia_case_study"]["dimension_sections"][0]["narrative"][0][
        "statement_origin"] = "evidence_derived"
    bad["ethiopia_case_study"]["dimension_sections"][0]["narrative"][0][
        "evidence_ids"] = []
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


def test_validation_rejects_traceability_drift(draft):
    bad = copy.deepcopy(draft)
    bad["traceability"][0]["section_id"] = "somewhere_else"
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


def test_validation_rejects_bad_gap_ref(draft):
    bad = copy.deepcopy(draft)
    bad["gaps"]["research_guidance"][0]["gap_id"] = "KENYA-not-a-gap"
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


def test_validation_rejects_fabricated_rating(draft):
    bad = copy.deepcopy(draft)
    bad["discussion"]["points"][0]["claims"][0]["statement"] = (
        bad["discussion"]["points"][0]["claims"][0]["statement"] + " scored 9.5.")
    with pytest.raises(ValueError):
        validate_academic_draft(bad)


# ---------------------------------------------------------------------------
# Regression: other cases and serialization
# ---------------------------------------------------------------------------

def test_draft_kenya_validates(committed_db):
    d = build_academic_draft("Kenya")
    validate_academic_draft(d)
    assert d["ethiopia_case_study"]["case"]["jurisdiction"] == "Kenya"


def test_draft_comparators_accepted(committed_db):
    d = build_academic_draft("Ethiopia", comparators=["Kenya"])
    validate_academic_draft(d)
    assert d["case_selection"]["comparators"] == ["Kenya"]


def test_serialization_roundtrip(draft):
    data = json.loads(academic_to_json(draft))
    assert data["academic_type"] == ACADEMIC_TYPE
    assert len(data["ethiopia_case_study"]["dimension_sections"]) == 12


def _discover():
    from src.governance.research_gaps import discover_gaps
    return discover_gaps()