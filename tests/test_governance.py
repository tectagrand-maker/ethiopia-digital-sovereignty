import json

import pytest

from src.evidence.models import GovernanceObservation, EvidenceObservation
from src.evidence.ingestion import ingest_evidence
from src.evidence.collection import add_source
from src.governance.analysis import create_observation, get_comparative_data, comparison_to_json, comparison_to_csv


def _source(jurisdiction="Ethiopia", url="https://example.com/a"):
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
        "title": "Ev " + s.url,
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "country_or_jurisdiction": s.jurisdiction,
        "domain_theme": "data_governance",
        "claim": "claim",
        "evidence_summary": "summary",
        "reliability_level": 3,
        "evidence_strength": 3,
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


def test_observation_persistence():
    s = _source()
    e = _evidence(s)
    obs = create_observation(_obs_data(), [e.evidence_id])
    assert obs.observation_id is not None
    row = GovernanceObservation.get(GovernanceObservation.observation_id == obs.observation_id)
    assert row.dimension == "data_governance"
    assert row.jurisdiction == "Ethiopia"


def test_observation_evidence_linkage():
    s = _source()
    e1 = _evidence(s, {"title": "EvA"})
    e2 = _evidence(s, {"title": "EvB"})
    obs = create_observation(_obs_data(), [e1.evidence_id, e2.evidence_id])
    assert obs.evidence_links.count() == 2
    linked = {eo.evidence.evidence_id for eo in obs.evidence_links}
    assert linked == {e1.evidence_id, e2.evidence_id}


def test_observation_invalid_evidence_reference():
    with pytest.raises(ValueError):
        create_observation(_obs_data(), [999999])


def test_observation_invalid_dimension():
    s = _source()
    e = _evidence(s)
    with pytest.raises(ValueError):
        create_observation(_obs_data(dimension="not_a_dimension"), [e.evidence_id])


def test_observation_invalid_confidence():
    s = _source()
    e = _evidence(s)
    with pytest.raises(ValueError):
        create_observation(_obs_data(confidence=99), [e.evidence_id])


def test_comparison_with_observations_and_missing_evidence():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/alpha")
    e_a = _evidence(s_a, {"domain_theme": "data_governance"})
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])

    data = get_comparative_data("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in data["dimensions"]}

    assert by_dim["data_governance"]["Alpha"]["status"] == "evidence_available"
    assert by_dim["data_governance"]["Beta"]["status"] == "missing_evidence"
    # Missing evidence must never become a score.
    assert by_dim["data_governance"]["Beta"]["assessment"] is None
    assert by_dim["data_governance"]["Beta"]["confidence"] is None
    # A dimension with no observation on either side is missing for both.
    assert by_dim["transparency"]["Alpha"]["status"] == "missing_evidence"


def test_comparison_retrieves_linked_evidence():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/alpha2")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])
    data = get_comparative_data("Alpha", "Beta")
    by_dim = {d["dimension"]: d for d in data["dimensions"]}
    obs = by_dim["data_governance"]["Alpha"]["observations"][0]
    assert obs["evidence_ids"] == [e_a.evidence_id]
    assert obs["evidence"][0]["evidence_id"] == e_a.evidence_id


def test_comparison_json_output_is_serializable_and_deterministic():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/alpha3")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])

    json.loads(comparison_to_json(get_comparative_data("Alpha", "Beta")))
    first = comparison_to_json(get_comparative_data("Alpha", "Beta"))
    second = comparison_to_json(get_comparative_data("Alpha", "Beta"))
    assert first == second


def test_comparison_csv_output():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/alpha4")
    e_a = _evidence(s_a)
    create_observation(_obs_data(jurisdiction="Alpha"), [e_a.evidence_id])
    csv_out = comparison_to_csv(get_comparative_data("Alpha", "Beta"))
    assert "dimension" in csv_out
    assert "data_governance" in csv_out
    assert "missing_evidence" in csv_out
