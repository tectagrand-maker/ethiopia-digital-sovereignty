"""Step 6: evidence basis, relations, matrices, baseline, status expansion."""

import json

import pytest

from src.evidence.models import Evidence, EvidenceRelation, GOVERNANCE_DIMENSIONS
from src.evidence.ingestion import ingest_evidence
from src.evidence.collection import add_source
from src.governance.analysis import (
    create_observation, create_evidence_relation, get_evidence_relations,
    comparative_baseline,
)
from src.governance.matrix import (
    coverage_matrix, research_matrix, matrix_to_csv, _derive_status,
)
from src.governance.status import research_status_report, report_to_json


def _source(jurisdiction="Ethiopia", url=None):
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
    }
    data.update(overrides or {})
    return ingest_evidence(data, s.source_id)


def _obs_data(jurisdiction="Ethiopia", dimension="data_governance", confidence=3):
    return {
        "jurisdiction": jurisdiction,
        "system_name": "System",
        "dimension": dimension,
        "indicator": "indicator_1",
        "observed_evidence": "observed",
        "assessment": "assessment text",
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Evidence basis classification
# ---------------------------------------------------------------------------

def test_evidence_basis_accepted():
    s = _source()
    e = _evidence(s, {"evidence_basis": "implementation"})
    assert e.evidence_basis == "implementation"


def test_evidence_basis_invalid_rejected():
    s = _source()
    with pytest.raises(ValueError):
        _evidence(s, {"evidence_basis": "not_a_basis"})


def test_evidence_basis_defaults_to_none():
    s = _source()
    e = _evidence(s, {"evidence_basis": None})
    assert e.evidence_basis is None


# ---------------------------------------------------------------------------
# Evidence relations
# ---------------------------------------------------------------------------

def test_create_evidence_relation():
    s = _source()
    e1 = _evidence(s, {"title": "EvA"})
    e2 = _evidence(s, {"title": "EvB"})
    rel = create_evidence_relation(e1.evidence_id, e2.evidence_id, "contradicts", "notes")
    assert rel.relation_type == "contradicts"
    assert rel.notes == "notes"


def test_create_evidence_relation_invalid_type():
    s = _source()
    e1 = _evidence(s, {"title": "EvA"})
    e2 = _evidence(s, {"title": "EvB"})
    with pytest.raises(ValueError):
        create_evidence_relation(e1.evidence_id, e2.evidence_id, "supports_everything")


def test_create_evidence_relation_missing_evidence():
    s = _source()
    e1 = _evidence(s, {"title": "EvA"})
    with pytest.raises(ValueError):
        create_evidence_relation(e1.evidence_id, 999999, "supports")


def test_get_evidence_relations_both_directions():
    s = _source()
    e1 = _evidence(s, {"title": "EvA"})
    e2 = _evidence(s, {"title": "EvB"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "qualifies")
    from_1 = get_evidence_relations(e1.evidence_id)
    from_2 = get_evidence_relations(e2.evidence_id)
    assert len(from_1) == 1 and from_1[0]["related_evidence_id"] == e2.evidence_id
    assert len(from_2) == 1 and from_2[0]["related_evidence_id"] == e1.evidence_id
    assert from_2[0]["relation_type"] == "qualifies"


# ---------------------------------------------------------------------------
# Comparative baseline
# ---------------------------------------------------------------------------

def _both_available(conf_a=5, conf_b=5, dim="data_governance"):
    s_a = _source(jurisdiction="Alpha", url="https://example.com/b-a")
    s_b = _source(jurisdiction="Beta", url="https://example.com/b-b")
    e_a = _evidence(s_a)
    e_b = _evidence(s_b)
    create_observation(_obs_data(jurisdiction="Alpha", dimension=dim, confidence=conf_a), [e_a.evidence_id])
    create_observation(_obs_data(jurisdiction="Beta", dimension=dim, confidence=conf_b), [e_b.evidence_id])


def test_baseline_similar_pattern():
    _both_available(conf_a=5, conf_b=4)
    result = comparative_baseline("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in result["dimensions"]}
    assert by_dim["data_governance"]["comparison_note"] == "similar_pattern"


def test_baseline_different_pattern():
    _both_available(conf_a=5, conf_b=2)
    result = comparative_baseline("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in result["dimensions"]}
    assert by_dim["data_governance"]["comparison_note"] == "different_pattern"


def test_baseline_insufficient_evidence():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/c-a")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])
    result = comparative_baseline("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in result["dimensions"]}
    assert by_dim["data_governance"]["comparison_note"] == "insufficient_evidence"


def test_baseline_not_comparable():
    result = comparative_baseline("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in result["dimensions"]}
    assert by_dim["data_governance"]["comparison_note"] == "not_comparable"


def test_baseline_never_scores():
    _both_available(conf_a=5, conf_b=2)
    result = comparative_baseline("Alpha", "Beta")
    payload = json.dumps(result)
    assert '"score"' not in payload
    assert '"score_alpha"' not in payload
    for dim in result["dimensions"]:
        assert "score" not in dim["Alpha"]
        assert "score" not in dim["Beta"]
        assert "ranking" not in dim


# ---------------------------------------------------------------------------
# Coverage matrix
# ---------------------------------------------------------------------------

def test_derive_status():
    assert _derive_status(2, 2) == "supported"
    assert _derive_status(1, 1) == "partial"
    assert _derive_status(0, 0) == "missing_evidence"


def test_coverage_matrix_supported_partial_missing():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/d-1")
    s2 = _source(jurisdiction="Alpha", url="https://example.com/d-2")
    _evidence(s1, {"domain_theme": "consent", "title": "EvC1"})
    _evidence(s2, {"domain_theme": "consent", "title": "EvC2"})
    s3 = _source(jurisdiction="Beta", url="https://example.com/d-3")
    _evidence(s3, {"domain_theme": "consent", "title": "EvC3"})

    rows = coverage_matrix()
    cell = {(r["jurisdiction"], r["governance_dimension"]): r for r in rows}
    assert cell[("Alpha", "consent_individual_agency")]["status"] == "supported"
    assert cell[("Beta", "consent_individual_agency")]["status"] == "partial"
    assert cell[("Alpha", "transparency")]["status"] == "missing_evidence"


def test_coverage_matrix_rows_are_deterministic():
    s1 = _source(jurisdiction="Alpha", url="https://example.com/e-1")
    _evidence(s1, {"domain_theme": "consent"})
    first = coverage_matrix()
    second = coverage_matrix()
    assert first == second


# ---------------------------------------------------------------------------
# Research matrix
# ---------------------------------------------------------------------------

def test_research_matrix_confidence_averaging():
    s1 = _source(jurisdiction="Ethiopia", url="https://example.com/f-1")
    s2 = _source(jurisdiction="Ethiopia", url="https://example.com/f-2")
    e1 = _evidence(s1, {"domain_theme": "consent", "title": "EvF1"})
    e2 = _evidence(s2, {"domain_theme": "consent", "title": "EvF2"})
    create_observation(_obs_data(jurisdiction="Ethiopia", dimension="consent_individual_agency", confidence=4),
                       [e1.evidence_id, e2.evidence_id])

    result = research_matrix(jurisdiction="Ethiopia")
    by_dim = {d["dimension"]: d for d in result["matrix"]}
    cell = by_dim["consent_individual_agency"]
    assert cell["status"] == "supported"
    assert cell["confidence"] == 4
    assert cell["observation_count"] == 1
    assert len(cell["evidence_ids"]) == 2


def test_research_matrix_missing_dimensions():
    result = research_matrix(jurisdiction="Ethiopia")
    by_dim = {d["dimension"]: d for d in result["matrix"]}
    assert by_dim["transparency"]["status"] == "missing_evidence"
    assert by_dim["transparency"]["confidence"] is None
    assert len(by_dim["transparency"]["key_supported_claims"]) == 0
    assert set(by_dim.keys()) == set(GOVERNANCE_DIMENSIONS)


def test_research_matrix_key_supported_claims():
    s1 = _source(jurisdiction="Ethiopia", url="https://example.com/g-1")
    e1 = _evidence(s1, {"claim": "Authoritative claim text", "title": "EvG1"})
    create_observation(_obs_data(jurisdiction="Ethiopia"), [e1.evidence_id])
    result = research_matrix(jurisdiction="Ethiopia")
    by_dim = {d["dimension"]: d for d in result["matrix"]}
    assert "Authoritative claim text" in by_dim["data_governance"]["key_supported_claims"]


def test_matrix_to_csv():
    s1 = _source(jurisdiction="Ethiopia", url="https://example.com/h-1")
    _evidence(s1, {"domain_theme": "consent"})
    csv_out = matrix_to_csv(research_matrix(jurisdiction="Ethiopia"))
    assert "dimension" in csv_out
    assert "consent_individual_agency" in csv_out


# ---------------------------------------------------------------------------
# Status report expansion
# ---------------------------------------------------------------------------

def test_status_locator_completeness():
    s = _source()
    _evidence(s, {"title": "WithLoc", "locator_type": "page", "locator_value": "4"})
    _evidence(s, {"title": "NoLoc", "locator_type": None, "locator_value": None})
    report = research_status_report()
    assert report["evidence"]["with_locators"] == 1
    missing = report["evidence"]["missing_locators"]
    assert len(missing) == 1
    missing_id = missing[0]
    assert Evidence.get(Evidence.evidence_id == missing_id).title == "NoLoc"


def test_status_single_and_multi_source():
    s1 = _source(url="https://example.com/i-1")
    s2 = _source(url="https://example.com/i-2")
    e1 = _evidence(s1, {"title": "EvI1"})
    e2 = _evidence(s2, {"title": "EvI2"})
    single = create_observation(_obs_data(dimension="data_governance"), [e1.evidence_id])
    multi = create_observation(_obs_data(dimension="transparency"), [e1.evidence_id, e2.evidence_id])

    report = research_status_report()
    gov = report["governance"]
    assert single.observation_id in gov["single_source_observations"]
    assert multi.observation_id in gov["multi_source_observations"]
    assert single.observation_id not in gov["multi_source_observations"]


def test_status_weak_support_low_confidence():
    s = _source()
    e = _evidence(s)
    weak = create_observation(_obs_data(confidence=2), [e.evidence_id])
    report = research_status_report()
    assert weak.observation_id in report["governance"]["weak_support_observations"]


def test_status_reports_unresolved_contradictions():
    s = _source()
    e1 = _evidence(s, {"title": "EvJ1"})
    e2 = _evidence(s, {"title": "EvJ2"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "contradicts", "conflict")
    report = research_status_report()
    assert len(report["gaps"]["unresolved_contradictions"]) == 1
    assert report["gaps"]["unresolved_contradictions"][0]["notes"] == "conflict"


def test_status_report_to_json():
    report = research_status_report()
    parsed = json.loads(report_to_json(report))
    assert parsed["report_type"] == "research_status"


def test_status_sources_with_evidence():
    s = _source()
    _evidence(s)
    report = research_status_report()
    assert report["sources"]["coverage"]["sources_with_evidence"] >= 1
    assert s.source_id not in report["sources"]["without_extracted_evidence"]
