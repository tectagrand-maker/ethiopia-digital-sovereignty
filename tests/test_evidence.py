import pytest

from src.evidence.models import Evidence
from src.evidence.ingestion import ingest_evidence
from src.evidence.collection import add_source


def _source():
    return add_source({
        "title": "Source for evidence",
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "jurisdiction": "Ethiopia",
        "url": "https://example.com/law",
    })


def _evidence(overrides=None):
    data = {
        "title": "Evidence item",
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "country_or_jurisdiction": "Ethiopia",
        "domain_theme": "digital_identity",
        "claim": "A claim supported by the source",
        "evidence_summary": "A structured summary",
        "source_excerpt": "The exact words from the source.",
        "interpretation": "Analytical reading of the excerpt.",
        "reliability_level": 4,
        "evidence_strength": 4,
        "locator_type": "page",
        "locator_value": "12",
    }
    data.update(overrides or {})
    return data


def test_evidence_requires_source():
    with pytest.raises(ValueError):
        ingest_evidence(_evidence(), 99999)


def test_evidence_valid_insertion_and_retrieval():
    s = _source()
    e = ingest_evidence(_evidence(), s.source_id)
    assert e is not None
    fetched = Evidence.get(Evidence.evidence_id == e.evidence_id)
    assert fetched.source.source_id == s.source_id
    assert fetched.title == "Evidence item"


def test_evidence_locator_preserved():
    s = _source()
    e = ingest_evidence(_evidence({"locator_type": "section", "locator_value": "5.2"}), s.source_id)
    assert e.locator_type == "section"
    assert e.locator_value == "5.2"


def test_evidence_source_excerpt_and_interpretation_kept_separate():
    s = _source()
    e = ingest_evidence(_evidence(), s.source_id)
    assert e.source_excerpt == "The exact words from the source."
    assert e.interpretation == "Analytical reading of the excerpt."
    assert e.evidence_summary == "A structured summary"
    assert e.claim == "A claim supported by the source"


def test_evidence_invalid_domain_rejected():
    s = _source()
    with pytest.raises(ValueError):
        ingest_evidence(_evidence({"domain_theme": "not-a-domain"}), s.source_id)


def test_evidence_invalid_reliability_rejected():
    s = _source()
    with pytest.raises(ValueError):
        ingest_evidence(_evidence({"reliability_level": 9}), s.source_id)


def test_evidence_duplicate_rejected_within_source():
    s = _source()
    ingest_evidence(_evidence(), s.source_id)
    with pytest.raises(ValueError):
        ingest_evidence(_evidence(), s.source_id)


def test_evidence_invalid_locator_type_rejected():
    s = _source()
    with pytest.raises(ValueError):
        ingest_evidence(_evidence({"locator_type": "nonsense"}), s.source_id)


def test_evidence_data_status_default_real():
    s = _source()
    e = ingest_evidence(_evidence(), s.source_id)
    assert e.data_status == "real"


def test_evidence_data_status_synthetic_allowed():
    s = _source()
    e = ingest_evidence(_evidence({"data_status": "synthetic",
                                   "notes": "DEMONSTRATION DATA ONLY."}), s.source_id)
    assert e.data_status == "synthetic"
