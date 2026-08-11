"""Step 10: targeted evidence acquisition closing prior research gaps.

Verifies the committed corpus (catalog + evidence + observations manifests)
after the Step 10 acquisition round, and the resulting derived statuses:

- Ethiopia transparency, interoperability and data_localization cells were
  previously `missing_evidence`/`partial` with high-priority research gaps;
  after acquisition they are `supported`.
- The European Union data_localization comparator cell is now `partial`.
- Source 17 (Freedom of the Mass Media and Access to Information Proclamation
  No. 590/2008) is registered as a discovered source.
- Evidence ids 26-33 map to the Step 10 records with the expected sources.
"""

import json
import os

import pytest

from src.evidence.collection import import_source_manifest
from src.evidence.ingestion import import_from_json
from src.evidence.models import Evidence, Source
from src.governance.analysis import create_observation
from src.governance.comparison import comparative_analysis
from src.governance.matrix import research_matrix
from src.governance.research_gaps import discover_gaps

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


@pytest.fixture()
def committed_db(eds_test_db):
    """Load the committed manifests into the isolated test DB (mirrors
    scripts/rebuild_db.py but bound to the temp database)."""
    import_source_manifest(os.path.join(DATA, "sources", "catalog.json"))

    with open(os.path.join(DATA, "evidence", "corpus_manifest.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    for entry in manifest:
        path = os.path.join(DATA, "evidence", entry["file"])
        import_from_json(path, entry["source_id"])

    with open(os.path.join(DATA, "evidence", "observations_manifest.json"),
              encoding="utf-8") as f:
        obs_manifest = json.load(f)
    for entry in obs_manifest:
        create_observation(entry["observation"], entry["evidence_ids"])
    return eds_test_db


def _titles():
    return {e.evidence_id: e.title for e in Evidence.select()}


def test_step10_committed_counts(committed_db):
    assert Source.select().count() == 17
    assert Evidence.select().count() == 33
    # 13 observations pre-Step 10 + 4 new governance observations
    assert len(json.load(open(os.path.join(DATA, "evidence",
                                           "observations_manifest.json"),
                              encoding="utf-8"))) == 17


def test_step10_new_source_registered(committed_db):
    s = Source.get(Source.source_id == 17)
    assert "590/2008" in s.title
    assert s.jurisdiction == "Ethiopia"
    assert s.source_type == "law"
    assert s.status == "discovered"


def test_step10_evidence_ids_map_to_new_records(committed_db):
    titles = _titles()
    assert titles[26].startswith("Digital Ethiopia 2025: online payments")
    assert titles[27].startswith("Digital Ethiopia 2025: no regulation of data centres")
    assert titles[28].startswith("World Bank ID4D: NIDP runs community information campaigns")
    assert titles[29].startswith("UNECA: internet shutdowns")
    assert titles[30].startswith("UNECA: before 2024 no legislation regulated cross-border")
    assert titles[31].startswith("UNECA: interconnection between telecom providers")
    assert titles[32].startswith("GDPR: free movement of personal data")
    assert titles[33].startswith("Proclamation 590/2008: right of access to information")


def test_step10_new_evidence_sources(committed_db):
    for eid, src_id in ((26, 5), (27, 5), (28, 9), (29, 10), (30, 10),
                        (31, 10), (32, 13), (33, 17)):
        e = Evidence.get(Evidence.evidence_id == eid)
        assert e.source.source_id == src_id
        assert e.data_status == "real"


def test_step10_new_evidence_locators_and_basis(committed_db):
    by_id = {e.evidence_id: e for e in Evidence.select()}
    assert by_id[26].locator_value == "p.59"
    assert by_id[27].locator_value == "p.62"
    assert by_id[28].locator_value == "p.21"
    assert by_id[29].locator_value == "p.6"
    assert by_id[30].locator_value == "p.6"
    assert by_id[31].locator_value == "p.4"
    assert by_id[32].locator_value == "Article 1(3)"
    assert by_id[33].locator_value == "Articles 12-13"
    assert by_id[30].evidence_basis == "empirical"
    assert by_id[31].evidence_basis == "institutional"
    assert by_id[32].evidence_basis == "normative"
    assert by_id[33].evidence_basis == "normative"


def test_step10_ethiopia_cells_supported(committed_db):
    matrix = research_matrix(jurisdiction="Ethiopia")
    by_dim = {d["dimension"]: d for d in matrix["matrix"]}
    assert by_dim["transparency"]["status"] == "supported"
    assert by_dim["transparency"]["evidence_count"] == 3
    assert set(by_dim["transparency"]["evidence_ids"]) == {28, 29, 33}
    assert by_dim["interoperability"]["status"] == "supported"
    assert by_dim["interoperability"]["evidence_count"] == 2
    assert set(by_dim["interoperability"]["evidence_ids"]) == {26, 31}
    assert by_dim["data_localization"]["status"] == "supported"
    assert by_dim["data_localization"]["evidence_count"] == 3
    assert set(by_dim["data_localization"]["evidence_ids"]) == {2, 27, 30}


def test_step10_prior_gaps_resolved(committed_db):
    gaps = discover_gaps()
    ids = [g["gap_id"] for g in gaps]
    resolved = [
        "ETHIOPIA-transparency-evidence_coverage",
        "ETHIOPIA-interoperability-evidence_coverage",
        "ETHIOPIA-data_localization-source_diversity",
        "ETHIOPIA-data_localization-methodological_limitation",
        "EUROPEAN_UNION-data_localization-evidence_coverage",
    ]
    for gap_id in resolved:
        assert gap_id not in ids, f"{gap_id} should be resolved by Step 10"


def test_step10_eu_data_localization_partial(committed_db):
    report = comparative_analysis(["Ethiopia", "European Union"])
    dims = {d["dimension"]: d for d in report["dimensions"]}
    eu = dims["data_localization"]["cases"]["European Union"]
    assert eu["evidence_status"] == "partial"
    assert eu["evidence_count"] == 1
    assert eu["evidence"][0]["evidence_id"] == 32
    eth = dims["data_localization"]["cases"]["Ethiopia"]
    assert eth["evidence_status"] == "supported"
    assert sorted(e["evidence_id"] for e in eth["evidence"]) == [2, 27, 30]
