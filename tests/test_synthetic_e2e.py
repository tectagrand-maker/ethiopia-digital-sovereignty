import json

from src.evidence.collection import add_source
from src.evidence.ingestion import _import_records
from src.governance.analysis import create_observation, get_comparative_data, comparison_to_json


def test_synthetic_end_to_end_flow(eds_test_db):
    """Fully synthetic demonstration: source -> evidence -> observation -> comparison -> JSON.

    Everything in this test is DEMONSTRATION DATA and must be labelled as such.
    """
    source = add_source({
        "title": "SYNTHETIC DEMO SOURCE - Example System Alpha",
        "source_type": "technical_report",
        "publisher_or_author": "SYNTHETIC DEMO",
        "publication_date": "2024-01-01",
        "jurisdiction": "Alpha",
        "url": "https://example.invalid/synthetic-alpha",
        "jurisdiction_group": "comparative",
        "data_status": "synthetic",
        "notes": "DEMONSTRATION DATA ONLY. Do not cite as real research.",
    })
    assert source.data_status == "synthetic"

    summary = _import_records([{
        "title": "SYNTHETIC DEMO EVIDENCE - Alpha transparency register",
        "source_type": "technical_report",
        "publisher_or_author": "SYNTHETIC DEMO",
        "publication_date": "2024-01-01",
        "country_or_jurisdiction": "Alpha",
        "domain_theme": "data_governance",
        "claim": "SYNTHETIC DEMO claim.",
        "evidence_summary": "SYNTHETIC DEMO summary.",
        "reliability_level": 1,
        "evidence_strength": 1,
        "data_status": "synthetic",
        "notes": "DEMONSTRATION DATA ONLY.",
    }], source.source_id)
    assert summary["accepted"] == 1

    from src.evidence.models import Evidence
    evidence = Evidence.get(Evidence.source == source)
    obs = create_observation({
        "jurisdiction": "Alpha",
        "system_name": "Alpha",
        "dimension": "data_governance",
        "indicator": "transparency_register",
        "observed_evidence": "SYNTHETIC DEMO observed evidence.",
        "assessment": "SYNTHETIC DEMO assessment - not a real finding.",
        "confidence": 2,
        "data_status": "synthetic",
        "analytical_notes": "DEMONSTRATION DATA ONLY.",
    }, [evidence.evidence_id])
    assert obs.evidence_links.count() == 1

    data = get_comparative_data("Alpha", "Beta")
    json_output = comparison_to_json(data)
    parsed = json.loads(json_output)
    by_dim = {d["dimension"]: d for d in parsed["dimensions"]}
    assert by_dim["data_governance"]["Alpha"]["status"] == "evidence_available"
    assert by_dim["data_governance"]["Alpha"]["observations"][0]["data_status"] == "synthetic"
    assert by_dim["data_governance"]["Beta"]["status"] == "missing_evidence"
