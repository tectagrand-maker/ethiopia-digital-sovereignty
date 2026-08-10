"""Step 7: comparative governance analysis tests.

Covers valid comparisons, evidence traceability, missing evidence, conflicting
evidence, deterministic output, schema/integrity constraints, and regression
against the Step 6 comparative/status/matrix functionality.
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
from src.governance.comparison import (
    available_cases, case_summary, case_dimension_view, comparative_analysis,
    validate_report, analysis_to_json, analysis_to_csv,
)
from src.governance.matrix import research_matrix
from src.governance.status import research_status_report


def _source(jurisdiction="Alpha", url=None):
    url = url or "https://example.com/" + jurisdiction + str(abs(hash(jurisdiction)) % 100000)
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
# Case discovery and profiles
# ---------------------------------------------------------------------------

def test_available_cases_empty():
    assert available_cases() == []


def test_available_cases_detects_evidence_jurisdictions():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/ca-1")
    s2 = _source(jurisdiction="Beta", url="https://example.com/ca-2")
    _evidence(s1)
    _evidence(s2, {"domain_theme": "consent"})
    assert available_cases() == ["Alpha", "Beta"]


def test_case_summary_counts():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/cs-1")
    s2 = _source(jurisdiction="Alpha", url="https://example.com/cs-2")
    _evidence(s1, {"domain_theme": "consent"})
    _evidence(s2, {"domain_theme": "consent"})
    summary = case_summary("Alpha")
    assert summary["jurisdiction"] == "Alpha"
    assert summary["evidence_count"] == 2
    assert summary["source_count"] == 2
    assert "consent_individual_agency" in summary["dimensions_with_evidence"]


# ---------------------------------------------------------------------------
# Cell views: statuses, traceability, missing/conflicting evidence
# ---------------------------------------------------------------------------

def test_cell_supported_status():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/v1")
    s2 = _source(jurisdiction="Alpha", url="https://example.com/v2")
    _evidence(s1, {"domain_theme": "consent"})
    _evidence(s2, {"domain_theme": "consent"})
    view = case_dimension_view("Alpha", "consent_individual_agency")
    assert view["evidence_status"] == "supported"
    assert view["evidence_count"] == 2
    assert view["source_count"] == 2


def test_cell_partial_status():
    s = _source(jurisdiction="Alpha", url="https://example.com/v3")
    _evidence(s, {"domain_theme": "consent"})
    view = case_dimension_view("Alpha", "consent_individual_agency")
    assert view["evidence_status"] == "partial"
    assert view["evidence_count"] == 1


def test_cell_missing_evidence():
    view = case_dimension_view("Alpha", "transparency")
    assert view["evidence_status"] == "missing_evidence"
    assert view["evidence_count"] == 0
    assert view["confidence"] is None
    assert view["evidence"] == []
    assert view["interpretation"] == []
    assert "No real evidence records" in view["gaps"]


def test_cell_conflicting_status():
    s = _source(jurisdiction="Alpha", url="https://example.com/v4")
    e1 = _evidence(s, {"title": "EvConf1"})
    e2 = _evidence(s, {"title": "EvConf2"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "contradicts", "conflict note")
    view = case_dimension_view("Alpha", "data_governance")
    assert view["evidence_status"] == "conflicting"
    assert view["conflicts"] == [{"evidence_a": e1.evidence_id,
                                  "evidence_b": e2.evidence_id,
                                  "notes": "conflict note"}]
    assert "Unresolved contradictions" in view["gaps"]


def test_cell_non_contradicting_relation_not_conflicting():
    s = _source(jurisdiction="Alpha", url="https://example.com/v5")
    e1 = _evidence(s, {"title": "EvSup1"})
    e2 = _evidence(s, {"title": "EvSup2"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "supports")
    view = case_dimension_view("Alpha", "data_governance")
    assert view["evidence_status"] != "conflicting"
    assert view["conflicts"] == []


def test_cell_evidence_traceability():
    s = _source(jurisdiction="Alpha", url="https://example.com/v6")
    e = _evidence(s, {"claim": "Traceable claim", "locator_value": "7"})
    view = case_dimension_view("Alpha", "data_governance")
    trace = view["evidence"][0]
    assert trace["evidence_id"] == e.evidence_id
    assert trace["source_id"] == s.source_id
    assert trace["locator_value"] == "7"
    assert trace["claim"] == "Traceable claim"
    assert trace["citation"] == "CIT " + s.url
    assert trace["source_url"] == s.url


def test_cell_interpretation_separate_from_evidence():
    s = _source(jurisdiction="Alpha", url="https://example.com/v7")
    e = _evidence(s)
    create_observation(_obs_data(jurisdiction="Alpha", confidence=4, assessment="Analytical assessment"),
                       [e.evidence_id])
    view = case_dimension_view("Alpha", "data_governance")
    assert view["interpretation"] == ["Analytical assessment"]
    assert view["confidence"] == 4
    assert "Analytical assessment" not in json.dumps(view["evidence"])


def test_cell_observation_count():
    s = _source(jurisdiction="Alpha", url="https://example.com/v8")
    e = _evidence(s)
    create_observation(_obs_data(jurisdiction="Alpha"), [e.evidence_id])
    view = case_dimension_view("Alpha", "data_governance")
    assert view["observation_count"] == 1


# ---------------------------------------------------------------------------
# Full comparative analysis report
# ---------------------------------------------------------------------------

def test_report_covers_all_dimensions():
    report = comparative_analysis(["Alpha"])
    assert report["report_type"] == "comparative_analysis"
    assert [d["dimension"] for d in report["dimensions"]] == list(GOVERNANCE_DIMENSIONS)
    assert report["cases"][0]["jurisdiction"] == "Alpha"


def test_report_default_cases_from_db():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/r1")
    s2 = _source(jurisdiction="Beta", url="https://example.com/r2")
    _evidence(s1)
    _evidence(s2, {"domain_theme": "consent"})
    report = comparative_analysis()
    assert [c["jurisdiction"] for c in report["cases"]] == ["Alpha", "Beta"]


def test_report_evidence_ids_present_per_cell():
    s = _source(jurisdiction="Alpha", url="https://example.com/r2")
    e = _evidence(s, {"domain_theme": "consent"})
    report = comparative_analysis(["Alpha"])
    by_dim = {d["dimension"]: d for d in report["dimensions"]}
    cell = by_dim["consent_individual_agency"]["cases"]["Alpha"]
    ids = [t["evidence_id"] for t in cell["evidence"]]
    assert e.evidence_id in ids


def test_report_deterministic():
    s = _source(jurisdiction="Alpha", url="https://example.com/r3")
    _evidence(s, {"domain_theme": "consent"})
    first = analysis_to_json(comparative_analysis(["Alpha"]))
    second = analysis_to_json(comparative_analysis(["Alpha"]))
    assert first == second


def test_report_cases_sorted_deterministic():
    s1 = _source(jurisdiction="Zeta", url="https://example.com/r4")
    s2 = _source(jurisdiction="Alpha", url="https://example.com/r5")
    _evidence(s1)
    _evidence(s2)
    report = comparative_analysis(["Zeta", "Alpha"])
    assert [c["jurisdiction"] for c in report["cases"]] == ["Alpha", "Zeta"]


def test_report_comparison_notes_pairwise():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/r6")
    s2 = _source(jurisdiction="Beta", url="https://example.com/r7")
    e1 = _evidence(s1, {"domain_theme": "consent"})
    e2 = _evidence(s2, {"domain_theme": "consent"})
    create_observation(_obs_data(jurisdiction="Alpha", dimension="consent_individual_agency", confidence=4),
                       [e1.evidence_id])
    create_observation(_obs_data(jurisdiction="Beta", dimension="consent_individual_agency", confidence=4),
                       [e2.evidence_id])
    report = comparative_analysis(["Alpha", "Beta"])
    by_dim = {d["dimension"]: d for d in report["dimensions"]}
    notes = by_dim["consent_individual_agency"]["comparison_notes"]
    assert notes == ["Alpha vs Beta: similar_pattern"]


def test_report_missing_evidence_is_not_a_score():
    report = comparative_analysis(["Alpha"])
    by_dim = {d["dimension"]: d for d in report["dimensions"]}
    cell = by_dim["transparency"]["cases"]["Alpha"]
    assert cell["evidence_status"] == "missing_evidence"
    assert cell["confidence"] is None
    assert '"score"' not in analysis_to_json(report)


def test_report_analytical_vs_evidence_distinction():
    s = _source(jurisdiction="Alpha", url="https://example.com/r8")
    e = _evidence(s)
    create_observation(_obs_data(jurisdiction="Alpha", assessment="Interpretive note"), [e.evidence_id])
    report = comparative_analysis(["Alpha"])
    by_dim = {d["dimension"]: d for d in report["dimensions"]}
    cell = by_dim["data_governance"]["cases"]["Alpha"]
    assert cell["evidence"]  # evidence list
    assert "Interpretive note" in cell["interpretation"]  # interpretation separate


# ---------------------------------------------------------------------------
# Schema / integrity constraints
# ---------------------------------------------------------------------------

def test_validate_report_accepts_valid():
    report = comparative_analysis([])
    model = validate_report(report)
    assert model.report_type == "comparative_analysis"


def test_validate_report_rejects_bad_status():
    s = _source(jurisdiction="Alpha", url="https://example.com/s1")
    e = _evidence(s)
    create_observation(_obs_data(jurisdiction="Alpha"), [e.evidence_id])
    report = comparative_analysis(["Alpha"])
    report["dimensions"][0]["cases"]["Alpha"]["evidence_status"] = "totally_great"
    with pytest.raises(ValidationError):
        validate_report(report)


def test_validate_report_rejects_missing_dimensions():
    report = comparative_analysis([])
    report["dimensions"] = report["dimensions"][:6]
    with pytest.raises(ValidationError):
        validate_report(report)


def test_validate_report_rejects_case_key_mismatch():
    s = _source(jurisdiction="Alpha", url="https://example.com/s2")
    _evidence(s)
    report = comparative_analysis(["Alpha"])
    report["dimensions"][0]["cases"]["Phantom"] = report["dimensions"][0]["cases"]["Alpha"]
    with pytest.raises(ValidationError):
        validate_report(report)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def test_analysis_csv_output():
    s = _source(jurisdiction="Alpha", url="https://example.com/c1")
    _evidence(s, {"domain_theme": "consent"})
    csv_out = analysis_to_csv(comparative_analysis(["Alpha"]))
    assert "dimension" in csv_out
    assert "data_governance" in csv_out
    assert "missing_evidence" in csv_out


def test_analysis_json_output_serializable():
    report = comparative_analysis([])
    payload = analysis_to_json(report)
    assert json.loads(payload)["report_type"] == "comparative_analysis"


# ---------------------------------------------------------------------------
# Regression against Step 6 functionality
# ---------------------------------------------------------------------------

def test_regression_get_comparative_data_still_works():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/reg-a")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])
    data = get_comparative_data("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in data["dimensions"]}
    assert by_dim["data_governance"]["Alpha"]["status"] == "evidence_available"
    assert by_dim["data_governance"]["Beta"]["status"] == "missing_evidence"


def test_regression_research_matrix_still_works():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/reg-m")
    _evidence(s, {"domain_theme": "consent"})
    result = research_matrix(jurisdiction="Ethiopia")
    assert len(result["matrix"]) == 12


def test_regression_research_status_still_works():
    report = research_status_report()
    assert report["report_type"] == "research_status"
    assert "governance" in report
