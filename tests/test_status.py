from src.governance.status import research_status_report


def test_research_status_counts_empty_db(eds_test_db):
    report = research_status_report()
    assert report["sources"]["total"] == 0
    assert report["evidence"]["total"] == 0
    assert report["governance"]["observations_total"] == 0
    # All 12 dimensions start with missing evidence.
    assert len(report["governance"]["dimensions_with_missing_evidence"]) == 12


def test_research_status_counts_with_data(eds_test_db):
    from src.evidence.collection import add_source
    from src.evidence.ingestion import ingest_evidence
    from src.governance.analysis import create_observation

    s = add_source({
        "title": "S", "source_type": "law", "publisher_or_author": "A",
        "publication_date": "2024-01-01", "jurisdiction": "ET",
        "url": "https://example.com/s", "jurisdiction_group": "ethiopia",
        "research_domains": "data_governance,digital_identity",
    })
    e = ingest_evidence({
        "title": "E", "source_type": "law", "publisher_or_author": "A",
        "publication_date": "2024-01-01", "country_or_jurisdiction": "ET",
        "domain_theme": "data_governance", "claim": "c", "evidence_summary": "s",
        "reliability_level": 3, "evidence_strength": 3,
    }, s.source_id)
    create_observation({
        "jurisdiction": "ET", "system_name": "Sys", "dimension": "data_governance",
        "indicator": "i", "observed_evidence": "o", "confidence": 3,
    }, [e.evidence_id])

    report = research_status_report()
    assert report["sources"]["total"] == 1
    assert report["sources"]["by_jurisdiction_group"]["ethiopia"] == 1
    assert report["evidence"]["total"] == 1
    assert report["governance"]["observations_total"] == 1
    assert report["governance"]["evidence_by_dimension"]["data_governance"] == 1
    assert "digital_identity" in report["governance"]["dimensions_with_missing_evidence"]
