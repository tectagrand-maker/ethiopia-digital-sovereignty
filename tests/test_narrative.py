r"""Step 12: Evidence-Traceable Case-Study Narrative.

Verifies the reproducible narrative layer built on the Step 8 dossier,
Step 11 findings and Step 9 gaps. Covers:

- deterministic, machine-readable narrative draft derived only from the database
- 12 dimension sections in the fixed governance-dimension order
- every claim carries evidence references (or is explicitly a corpus limitation)
- claim origins stay in the controlled vocabulary
- comparative narrative blocks for evidenced pairs only
- cross-cutting patterns are never causal claims
- a traceability manifest that exactly matches the referenced evidence
- research guidance resolving against the live gap inventory
- a deterministic markdown rendering with inline evidence citations
- full integrity validation against schema and database
"""

import copy
import json
import os

import pytest
from pydantic import ValidationError

from src.evidence.collection import import_source_manifest
from src.evidence.ingestion import import_from_json
from src.evidence.models import Evidence
from src.governance.analysis import create_observation
from src.governance.findings import STATEMENT_ORIGINS
from src.governance.narrative import (
    case_study_narrative, validate_narrative, narrative_to_json,
    narrative_to_markdown,
)
from src.governance.research_gaps import discover_gaps
from src.evidence.models import GOVERNANCE_DIMENSIONS

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
def narrative(committed_db):
    return case_study_narrative("Ethiopia")


# ---------------------------------------------------------------------------
# Shape and determinism
# ---------------------------------------------------------------------------

def test_narrative_shape(narrative):
    assert narrative["narrative_type"] == "case_study_narrative"
    assert narrative["schema_version"] == 1
    assert narrative["note"]
    assert narrative["case"]["jurisdiction"] == "Ethiopia"
    assert sum(narrative["coverage_summary"].values()) == 12


def test_narrative_has_all_12_dimensions(narrative):
    dims = [s["dimension"] for s in narrative["dimension_sections"]]
    assert dims == list(GOVERNANCE_DIMENSIONS)


def test_narrative_deterministic(narrative):
    n2 = case_study_narrative("Ethiopia")
    assert narrative_to_json(narrative) == narrative_to_json(n2)


def test_narrative_no_timestamp_fields(narrative):
    assert not (set(narrative.keys()) & {"timestamp", "generated_at", "run_at"})


# ---------------------------------------------------------------------------
# Dimension sections
# ---------------------------------------------------------------------------

def test_narrative_section_origins_controlled(narrative):
    for sec in narrative["dimension_sections"]:
        for claim in sec["narrative"]:
            assert claim["statement_origin"] in STATEMENT_ORIGINS
        assert sec["evidence_status"] in {
            "supported", "partial", "missing_evidence", "conflicting"}


def test_narrative_section_status_matches_cell(narrative):
    from src.governance.comparison import case_dimension_view
    for sec in narrative["dimension_sections"]:
        view = case_dimension_view("Ethiopia", sec["dimension"])
        assert sec["evidence_status"] == view["evidence_status"]
        assert sec["evidence_count"] == view["evidence_count"]


def test_narrative_evidence_claims_traceable(narrative):
    for sec in narrative["dimension_sections"]:
        for claim in sec["narrative"]:
            if claim["statement_origin"] == "evidence_derived":
                assert claim["evidence_ids"], (
                    f"Evidence-derived claim {claim['claim_id']} has no refs.")
        for claim in sec["narrative"]:
            for eid in claim["evidence_ids"]:
                assert Evidence.get_or_none(Evidence.evidence_id == eid)


def test_narrative_missing_cell_is_limitation(narrative):
    by_dim = {s["dimension"]: s for s in narrative["dimension_sections"]}
    for dim, sec in by_dim.items():
        if sec["evidence_status"] == "missing_evidence":
            # at least one corpus_limitation claim present
            assert any(c["statement_origin"] == "corpus_limitation"
                       for c in sec["narrative"])
            assert any("not evidence of absence" in c["statement"].lower()
                       or "never a negative" in c["statement"].lower()
                       for c in sec["narrative"])


def test_narrative_interpretation_kept_separate(narrative):
    by_dim = {s["dimension"]: s for s in narrative["dimension_sections"]}
    sec = by_dim["data_localization"]
    interp = [c for c in sec["narrative"]
              if c["statement_origin"] == "analytical_interpretation"]
    assert interp
    # interpretation never becomes an evidence-derived claim
    for c in interp:
        assert c["statement_origin"] == "analytical_interpretation"


def test_narrative_no_scores_or_rankings(narrative):
    for sec in narrative["dimension_sections"]:
        for claim in sec["narrative"]:
            assert "score" not in claim["statement"].lower()
            assert "rank" not in claim["statement"].lower()


def test_narrative_section_unique_claim_ids(narrative):
    for sec in narrative["dimension_sections"]:
        ids = [c["claim_id"] for c in sec["narrative"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Comparative, cross-cutting, synthesis
# ---------------------------------------------------------------------------

def test_narrative_comparative_sections_present(narrative):
    assert narrative["comparative_sections"]
    for sec in narrative["comparative_sections"]:
        assert len(sec["pair"]) == 2
        assert "Ethiopia" in sec["pair"]
        for claim in sec["narrative"]:
            assert claim["statement_origin"] in STATEMENT_ORIGINS


def test_narrative_cross_cutting_never_causal(narrative):
    for p in narrative["cross_cutting_patterns"]:
        # shared-source pattern must not claim causation
        if p["pattern"] == "shared_source_pattern":
            assert "not a causal link" in p["statement"]
        if p["pattern"] == "no_causal_inference":
            assert "does not" in p["statement"]


def test_narrative_synthesis_evidence_backed(narrative):
    syn = narrative["synthesis"]
    for claim in syn["major_supported_findings"] + syn["partial_findings"]:
        assert claim["evidence_ids"]
    assert len(syn["missing_evidence_areas"]) == 1


# ---------------------------------------------------------------------------
# Research guidance
# ---------------------------------------------------------------------------

def test_narrative_research_guidance_resolves(narrative):
    live = {g["gap_id"] for g in discover_gaps()}
    assert narrative["research_guidance"]
    for item in narrative["research_guidance"]:
        assert item["gap_id"] in live
        assert item["research_question"].endswith("?")


def test_narrative_guidance_priority_sorted(narrative):
    rank = {"high": 0, "medium": 1, "low": 2}
    levels = [rank[i["priority_level"]] for i in narrative["research_guidance"]]
    assert levels == sorted(levels)


# ---------------------------------------------------------------------------
# Traceability manifest
# ---------------------------------------------------------------------------

def test_narrative_traceability_matches_references(narrative):
    referenced = set()
    for sec in narrative["dimension_sections"]:
        for claim in sec["narrative"]:
            referenced.update(
                (eid, sec["section_id"]) for eid in claim["evidence_ids"])
    for sec in narrative["comparative_sections"]:
        for claim in sec["narrative"]:
            referenced.update(
                (eid, sec["section_id"]) for eid in claim["evidence_ids"])
    for p in narrative["cross_cutting_patterns"]:
        referenced.update(
            (eid, f"cross-cutting:{p['pattern']}") for eid in p["evidence_ids"])
    manifest = {(r["evidence_id"], r["section_id"])
                for r in narrative["traceability"]}
    assert manifest == referenced


def test_narrative_traceability_rows_unique(narrative):
    rows = [(r["evidence_id"], r["section_id"])
            for r in narrative["traceability"]]
    assert len(rows) == len(set(rows))


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def test_narrative_markdown_deterministic(narrative):
    md1 = narrative_to_markdown(narrative)
    md2 = narrative_to_markdown(case_study_narrative("Ethiopia"))
    assert md1 == md2
    assert "Case-Study Narrative Draft" in md1
    assert "[ev" in md1
    assert "Traceability manifest" in md1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_narrative_validation_passes(narrative):
    model = validate_narrative(narrative)
    assert model.narrative_type == "case_study_narrative"


def test_narrative_validation_rejects_bad_origin(narrative):
    bad = copy.deepcopy(narrative)
    bad["dimension_sections"][0]["narrative"][0]["statement_origin"] = "invented"
    with pytest.raises(ValidationError):
        validate_narrative(bad)


def test_narrative_validation_rejects_bad_dimension(narrative):
    bad = copy.deepcopy(narrative)
    bad["dimension_sections"][0]["dimension"] = "not_a_dimension"
    with pytest.raises(ValidationError):
        validate_narrative(bad)


def test_narrative_validation_rejects_orphan_evidence(narrative):
    bad = copy.deepcopy(narrative)
    bad["dimension_sections"][0]["narrative"][1]["evidence_ids"] = [9999]
    with pytest.raises(ValueError):
        validate_narrative(bad)


def test_narrative_validation_rejects_cross_cell_evidence(narrative):
    bad = copy.deepcopy(narrative)
    # inject Kenya-evidence id into an Ethiopia cell claim
    bad["dimension_sections"][0]["narrative"][1]["evidence_ids"] = [5]
    with pytest.raises(ValueError):
        validate_narrative(bad)


def test_narrative_validation_rejects_unsupported_claim(narrative):
    bad = copy.deepcopy(narrative)
    bad["dimension_sections"][0]["narrative"][0]["statement_origin"] = \
        "evidence_derived"
    bad["dimension_sections"][0]["narrative"][0]["evidence_ids"] = []
    with pytest.raises(ValueError):
        validate_narrative(bad)


def test_narrative_validation_rejects_bad_gap_ref(narrative):
    bad = copy.deepcopy(narrative)
    ref = dict(bad["dimension_sections"][0]["research_gap_refs"][0])
    ref["gap_id"] = "KENYA-data_governance-evidence_coverage"
    bad["dimension_sections"][0]["research_gap_refs"].append(ref)
    with pytest.raises(ValueError):
        validate_narrative(bad)


def test_narrative_validation_rejects_traceability_drift(narrative):
    bad = copy.deepcopy(narrative)
    bad["traceability"][0]["section_id"] = "somewhere_else"
    with pytest.raises(ValueError):
        validate_narrative(bad)


# ---------------------------------------------------------------------------
# Regression: Kenya and comparators
# ---------------------------------------------------------------------------

def test_narrative_kenya_validates(committed_db):
    n = case_study_narrative("Kenya")
    validate_narrative(n)
    assert all(s["dimension"] in GOVERNANCE_DIMENSIONS
               for s in n["dimension_sections"])


def test_narrative_comparators_accepted(committed_db):
    n = case_study_narrative("Ethiopia", comparators=["Kenya"])
    validate_narrative(n)
    for sec in n["comparative_sections"]:
        assert "Kenya" in sec["pair"] or "Ethiopia" in sec["pair"]


def test_narrative_serialization_roundtrip(narrative):
    text = narrative_to_json(narrative)
    data = json.loads(text)
    assert data["case"]["jurisdiction"] == "Ethiopia"
    assert len(data["dimension_sections"]) == 12