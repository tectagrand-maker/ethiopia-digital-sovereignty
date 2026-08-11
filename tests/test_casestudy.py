"""Step 8: evidence-backed case-study framework tests.

Covers case construction, dimension completeness, evidence traceability,
provenance validation, missing/conflicting evidence, research gaps,
deterministic serialization, comparative-context references, orphan/invalid
references, schema validation, CLI generation/validation, and regression
against the Step 6/7 machinery.
"""

import json

import pytest
from pydantic import ValidationError

from src.evidence.models import GOVERNANCE_DIMENSIONS
from src.evidence.ingestion import ingest_evidence
from src.evidence.collection import add_source
from src.governance.analysis import (
    create_observation, create_evidence_relation, get_comparative_data,
)
from src.governance.matrix import coverage_matrix, research_matrix
from src.governance.comparison import comparative_analysis
from src.governance.casestudy import (
    case_study_dossier, validate_dossier, dossier_to_json, dossier_to_markdown,
)
from src.cli import main


def _source(jurisdiction="Alpha", url=None):
    url = url or "https://example.com/cs-" + jurisdiction + str(abs(hash(jurisdiction)) % 100000)
    return add_source({
        "title": "Gov source " + url,
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "jurisdiction": jurisdiction,
        "url": url,
    })


def _evidence(s, overrides=None):
    data = {
        "title": "Ev " + s.url + str(abs(hash(str(overrides))) % 100000),
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "country_or_jurisdiction": s.jurisdiction,
        "domain_theme": "data_governance",
        "claim": "claim",
        "evidence_summary": "summary",
        "reliability_level": 3,
        "evidence_strength": 3,
        "evidence_basis": "normative",
        "locator_type": "page",
        "locator_value": "12",
        "citation": "CIT " + s.url,
    }
    data.update(overrides or {})
    return ingest_evidence(data, s.source_id)


def _obs_data(jurisdiction="Alpha", dimension="data_governance", confidence=3,
              assessment="assessment text"):
    return {
        "jurisdiction": jurisdiction,
        "system_name": "System",
        "dimension": dimension,
        "indicator": "indicator_1",
        "observed_evidence": "observed",
        "assessment": assessment,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Case construction and identity
# ---------------------------------------------------------------------------

def test_dossier_structure_and_identity():
    dossier = case_study_dossier("Alpha")
    assert dossier["dossier_type"] == "case_study_dossier"
    assert dossier["schema_version"] == 1
    assert dossier["case"]["jurisdiction"] == "Alpha"
    assert set(dossier["case"].keys()) >= {
        "title", "description", "source_count", "evidence_count",
        "available_dimensions", "coverage_summary",
    }
    assert set(dossier["case"]["coverage_summary"].keys()) == {
        "supported", "partial", "missing_evidence", "conflicting",
    }


def test_dossier_empty_case_all_missing():
    dossier = case_study_dossier("Phantom")
    assert dossier["case"]["evidence_count"] == 0
    assert dossier["case"]["coverage_summary"]["missing_evidence"] == 12
    statuses = {p["evidence_status"] for p in dossier["dimension_profiles"]}
    assert statuses == {"missing_evidence"}
    validate_dossier(dossier)


def test_dossier_identity_counts():
    s1 = _source(url="https://example.com/id-1")
    s2 = _source(url="https://example.com/id-2")
    _evidence(s1, {"domain_theme": "consent"})
    _evidence(s2, {"domain_theme": "consent"})
    dossier = case_study_dossier("Alpha")
    assert dossier["case"]["evidence_count"] == 2
    assert dossier["case"]["source_count"] == 2
    assert "consent_individual_agency" in dossier["case"]["available_dimensions"]
    assert dossier["case"]["coverage_summary"]["supported"] == 1


# ---------------------------------------------------------------------------
# Dimension completeness and profiling
# ---------------------------------------------------------------------------

def test_dossier_covers_all_dimensions():
    dossier = case_study_dossier("Alpha")
    assert [p["dimension"] for p in dossier["dimension_profiles"]] == list(GOVERNANCE_DIMENSIONS)
    for profile in dossier["dimension_profiles"]:
        assert set(profile.keys()) >= {
            "dimension", "evidence_status", "evidence_count", "source_count",
            "observation_count", "evidence", "observations", "interpretation",
            "analytical_notes", "conflicts", "research_gaps",
        }


def test_dimension_profile_traceability():
    s = _source(url="https://example.com/tr-1")
    e = _evidence(s, {"claim": "Traceable claim", "locator_value": "7",
                      "evidence_basis": "normative"})
    obs = create_observation(_obs_data(jurisdiction="Alpha", dimension="data_governance"),
                              [e.evidence_id])
    dossier = case_study_dossier("Alpha")
    profile = dossier["dimension_profiles"][0]
    trace = profile["evidence"][0]
    assert trace["evidence_id"] == e.evidence_id
    assert trace["source_id"] == s.source_id
    assert trace["claim"] == "Traceable claim"
    assert trace["locator_value"] == "7"
    assert trace["citation"] == "CIT " + s.url
    assert trace["source_url"] == s.url
    assert profile["observation_count"] == 1
    obs_ref = profile["observations"][0]
    assert obs_ref["observation_id"] == obs.observation_id
    assert e.evidence_id in obs_ref["evidence_ids"]


def test_dimension_profile_interpretation_separate_from_evidence():
    s = _source(url="https://example.com/sep-1")
    e = _evidence(s)
    create_observation(_obs_data(jurisdiction="Alpha", assessment="Analytical assessment",
                                 confidence=4), [e.evidence_id])
    dossier = case_study_dossier("Alpha")
    profile = dossier["dimension_profiles"][0]
    assert profile["interpretation"] == ["Analytical assessment"]
    assert profile["confidence"] == 4
    assert "Analytical assessment" not in json.dumps(profile["evidence"])


def test_missing_evidence_profile_has_gaps():
    dossier = case_study_dossier("Alpha")
    profile = next(p for p in dossier["dimension_profiles"]
                   if p["dimension"] == "transparency")
    assert profile["evidence_status"] == "missing_evidence"
    assert profile["evidence_count"] == 0
    assert profile["confidence"] is None
    assert profile["research_gaps"]
    assert "No real evidence records" in profile["research_gaps"][0]


def test_conflicting_evidence_propagates_to_synthesis():
    s = _source(url="https://example.com/cf-1")
    e1 = _evidence(s, {"title": "EvConfA"})
    e2 = _evidence(s, {"title": "EvConfB"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "contradicts", "conflict note")
    dossier = case_study_dossier("Alpha")
    profile = dossier["dimension_profiles"][0]
    assert profile["evidence_status"] == "conflicting"
    assert profile["conflicts"] == [{"evidence_a": e1.evidence_id,
                                     "evidence_b": e2.evidence_id,
                                     "notes": "conflict note"}]
    assert "Unresolved contradictions" in profile["research_gaps"][0]
    assert {"evidence_a": e1.evidence_id,
            "evidence_b": e2.evidence_id,
            "notes": "conflict note"} in dossier["synthesis"]["conflicting_evidence"]


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def test_synthesis_findings_reference_evidence():
    s = _source(url="https://example.com/sy-1")
    e = _evidence(s, {"domain_theme": "consent"})
    dossier = case_study_dossier("Alpha")
    findings = (dossier["synthesis"]["major_supported_findings"]
                + dossier["synthesis"]["partial_findings"])
    finding = next(f for f in findings if e.evidence_id in f["evidence_ids"])
    assert finding["source_ids"] == [s.source_id]
    assert finding["claim"]


def test_synthesis_missing_evidence_areas():
    s = _source(url="https://example.com/mi-1")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    assert "transparency" in dossier["synthesis"]["missing_evidence_areas"]
    gaps = dossier["synthesis"]["priority_research_gaps"]
    assert any("No evidence for dimension transparency" in g for g in gaps)
    assert any("not a negative finding" in g for g in dossier["synthesis"]["limitations"])


def test_synthesis_no_scores_or_rankings():
    dossier = case_study_dossier("Alpha")
    payload = dossier_to_json(dossier)
    assert '"score"' not in payload
    assert '"rank"' not in payload
    assert "coverage_summary" in dossier["case"]  # counts, not scores


# ---------------------------------------------------------------------------
# Deterministic serialization
# ---------------------------------------------------------------------------

def test_dossier_deterministic_json():
    s = _source(url="https://example.com/de-1")
    _evidence(s, {"domain_theme": "consent"})
    first = dossier_to_json(case_study_dossier("Alpha"))
    second = dossier_to_json(case_study_dossier("Alpha"))
    assert first == second


def test_dossier_markdown_renders():
    s = _source(url="https://example.com/md-1")
    _evidence(s, {"domain_theme": "consent"})
    md = dossier_to_markdown(case_study_dossier("Alpha"))
    assert "# Case Study Dossier: Alpha" in md
    assert "## consent_individual_agency" in md
    assert "## Synthesis" in md
    assert "## Comparative context" in md


# ---------------------------------------------------------------------------
# Comparative context references (Step 7, no duplication)
# ---------------------------------------------------------------------------

def test_comparative_context_default_comparators():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/cc-a")
    s_b = _source(jurisdiction="Beta", url="https://example.com/cc-b")
    _evidence(s_a)
    _evidence(s_b)
    ctx = case_study_dossier("Alpha")["comparative_context"]
    assert ctx["available_comparators"] == ["Beta"]
    assert "comparative" in ctx["note"]
    assert "Step 7" in ctx["note"]


def test_comparative_context_explicit_comparators():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/cc2-a")
    s_b = _source(jurisdiction="Beta", url="https://example.com/cc2-b")
    s_c = _source(jurisdiction="Gamma", url="https://example.com/cc2-c")
    _evidence(s_a)
    _evidence(s_b)
    _evidence(s_c)
    ctx = case_study_dossier("Alpha", comparators=["Gamma"])["comparative_context"]
    assert ctx["available_comparators"] == ["Gamma"]
    assert "Beta" not in ctx["available_comparators"]


def test_comparative_context_dimension_notes():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/cc3-a")
    s_b = _source(jurisdiction="Beta", url="https://example.com/cc3-b")
    e_a = _evidence(s_a, {"domain_theme": "consent"})
    e_b = _evidence(s_b, {"domain_theme": "consent"})
    create_observation(_obs_data(jurisdiction="Alpha", dimension="consent_individual_agency",
                                 confidence=4), [e_a.evidence_id])
    create_observation(_obs_data(jurisdiction="Beta", dimension="consent_individual_agency",
                                 confidence=4), [e_b.evidence_id])
    ctx = case_study_dossier("Alpha")["comparative_context"]
    assert "consent_individual_agency" in ctx["dimension_notes"]
    assert ctx["dimension_notes"]["consent_individual_agency"] == ["Alpha vs Beta: similar_pattern"]


# ---------------------------------------------------------------------------
# Validation: schema and database integrity
# ---------------------------------------------------------------------------

def test_validate_dossier_accepts_valid():
    s = _source(url="https://example.com/v-ok")
    e = _evidence(s, {"domain_theme": "consent"})
    create_observation(_obs_data(jurisdiction="Alpha", dimension="consent_individual_agency"),
                       [e.evidence_id])
    dossier = case_study_dossier("Alpha")
    model = validate_dossier(dossier)
    assert model.dossier_type == "case_study_dossier"
    assert model.case.evidence_count == 1


def test_validate_dossier_rejects_bad_status():
    s = _source(url="https://example.com/v-bs")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    dossier["dimension_profiles"][0]["evidence_status"] = "totally_great"
    with pytest.raises(ValidationError):
        validate_dossier(dossier)


def test_validate_dossier_rejects_missing_dimension():
    dossier = case_study_dossier("Alpha")
    dossier["dimension_profiles"] = dossier["dimension_profiles"][:6]
    with pytest.raises(ValidationError):
        validate_dossier(dossier)


def test_validate_dossier_rejects_orphan_evidence_ref():
    s = _source(url="https://example.com/v-or")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    dossier["dimension_profiles"][0]["evidence"][0]["evidence_id"] = 999999
    with pytest.raises(ValueError, match="[Oo]rphan"):
        validate_dossier(dossier)


def test_validate_dossier_rejects_jurisdiction_mismatch():
    s = _source(url="https://example.com/v-jm")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    dossier["case"]["jurisdiction"] = "Beta"
    with pytest.raises(ValueError, match="jurisdiction"):
        validate_dossier(dossier)


def test_validate_dossier_rejects_source_mismatch():
    s = _source(url="https://example.com/v-sm")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    dossier["dimension_profiles"][0]["evidence"][0]["source_id"] = 424242
    with pytest.raises(ValueError, match="source"):
        validate_dossier(dossier)


def test_validate_dossier_rejects_unsupported_synthesis():
    s = _source(url="https://example.com/v-us")
    _evidence(s)
    dossier = case_study_dossier("Alpha")
    dossier["synthesis"]["major_supported_findings"].append({
        "claim": "unsupported claim",
        "evidence_ids": [],
        "source_ids": [],
    })
    with pytest.raises(ValueError, match="without evidence"):
        validate_dossier(dossier)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_case_study_json(capsys, eds_test_db):
    s = _source(url="https://example.com/cli-1")
    _evidence(s, {"domain_theme": "consent"})
    main(["case-study", "--case", "Alpha"])
    data = json.loads(capsys.readouterr().out)
    assert data["dossier_type"] == "case_study_dossier"
    assert data["case"]["jurisdiction"] == "Alpha"


def test_cli_case_study_markdown(capsys, eds_test_db):
    s = _source(url="https://example.com/cli-2")
    _evidence(s, {"domain_theme": "consent"})
    main(["case-study", "--case", "Alpha", "--format", "markdown"])
    out = capsys.readouterr().out
    assert "# Case Study Dossier: Alpha" in out
    assert "## consent_individual_agency" in out


def test_cli_case_study_validate(capsys, eds_test_db):
    s = _source(url="https://example.com/cli-3")
    _evidence(s)
    main(["case-study", "--case", "Alpha", "--validate"])
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == 1


def test_cli_case_study_unknown_case_errors(capsys, eds_test_db):
    with pytest.raises(SystemExit):
        main(["case-study"])
    err = capsys.readouterr().err
    assert "case" in err


# ---------------------------------------------------------------------------
# Regression against Step 6/7
# ---------------------------------------------------------------------------

def test_regression_comparative_analysis_still_works():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/reg-a")
    s_b = _source(jurisdiction="Beta", url="https://example.com/reg-b")
    _evidence(s_a, {"domain_theme": "consent"})
    _evidence(s_b, {"domain_theme": "consent"})
    report = comparative_analysis(["Alpha", "Beta"])
    assert [c["jurisdiction"] for c in report["cases"]] == ["Alpha", "Beta"]


def test_regression_research_matrix_still_works():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/reg-m")
    _evidence(s, {"domain_theme": "consent"})
    assert len(research_matrix(jurisdiction="Ethiopia")["matrix"]) == 12


def test_regression_get_comparative_data_still_works():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/reg-gc")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])
    data = get_comparative_data("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in data["dimensions"]}
    assert by_dim["data_governance"]["Alpha"]["status"] == "evidence_available"
    assert by_dim["data_governance"]["Beta"]["status"] == "missing_evidence"


def test_regression_coverage_matrix_still_works():
    s = _source(jurisdiction="Alpha", url="https://example.com/reg-cm")
    _evidence(s, {"domain_theme": "consent"})
    rows = coverage_matrix()
    assert any(r["jurisdiction"] == "Alpha" and
               r["governance_dimension"] == "consent_individual_agency" for r in rows)
