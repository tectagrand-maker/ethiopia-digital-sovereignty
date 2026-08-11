r"""Step 11: Evidence Re-analysis & Research Findings Synthesis.

Verifies the reproducible findings layer built on the committed corpus
(Steps 6-10). Covers spec requirements for:

- deterministic, machine-readable report derived only from the database
- per-cell findings with controlled vocabularies and separate layers
  (evidence / observation / interpretation / limitation / research gap)
- explicit uncertainty and missing-evidence handling (never a negative finding)
- comparative findings only where both sides hold evidence
- cross-dimension, non-causal patterns
- Ethiopia as the primary-case synthesis
- committed resolved-gap record and remaining-gap consistency
- a deterministic markdown rendering
- full integrity validation against schema and database
"""

import copy
import json
import os

import pytest
from pydantic import ValidationError

from src.evidence.collection import import_source_manifest
from src.evidence.ingestion import import_from_json
from src.evidence.models import Evidence, Source
from src.governance.analysis import create_observation
from src.governance.comparison import comparative_analysis
from src.governance.findings import (
    FINDING_TYPES, STATEMENT_ORIGINS, CROSS_DIMENSION_PATTERNS,
    build_findings_report, validate_findings, findings_to_json,
    findings_to_markdown,
)
from src.governance.research_gaps import discover_gaps

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
        path = os.path.join(DATA, "evidence", entry["file"])
        import_from_json(path, entry["source_id"])

    with open(os.path.join(DATA, "evidence", "observations_manifest.json"),
              encoding="utf-8") as f:
        obs_manifest = json.load(f)
    for entry in obs_manifest:
        create_observation(entry["observation"], entry["evidence_ids"])
    return eds_test_db


@pytest.fixture()
def report(committed_db):
    return build_findings_report()


@pytest.fixture()
def gap_ids(committed_db):
    return {g["gap_id"] for g in discover_gaps()}


# ---------------------------------------------------------------------------
# Report shape and corpus state
# ---------------------------------------------------------------------------

def test_findings_report_shape(report):
    assert report["report_type"] == "evidence_findings_synthesis"
    assert report["schema_version"] == 1
    assert report["note"]
    assert sorted(d["dimension"] for d in report["dimensions"]) == sorted(
        [(d["dimension"]) for d in report["dimensions"]])
    assert len(report["dimensions"]) == 12


def test_findings_corpus_state_counts(report):
    cs = report["corpus_state"]
    assert cs["sources"] == 17
    assert cs["evidence"] == 33
    assert cs["observations"] == 17
    assert cs["relations"] == 0
    assert cs["cases"] == sorted(cs["cases"])
    assert len(cs["corpus_digest"]) == 64


def test_findings_no_timestamp_fields(report):
    text = findings_to_json(report)
    for forbidden in ("timestamp", "generated_at", "created_at"):
        assert json.loads(text).get(forbidden) is None
    report_keys = set(report.keys())
    assert not (report_keys & {"timestamp", "generated_at", "run_at"})


def test_findings_deterministic(report):
    report2 = build_findings_report()
    assert findings_to_json(report) == findings_to_json(report2)
    assert report["corpus_state"]["corpus_digest"] == \
        report2["corpus_state"]["corpus_digest"]


def test_findings_cases_include_all(report):
    jurisdictions = {c["jurisdiction"] for c in report["cases"]}
    assert jurisdictions == {"Ethiopia", "European Union", "Kenya"}


# ---------------------------------------------------------------------------
# Per-cell findings
# ---------------------------------------------------------------------------

def test_findings_one_per_cell(report):
    assert len(report["findings"]) == 3 * 12
    keys = [(f["finding_id"]) for f in report["findings"]]
    assert len(keys) == len(set(keys))
    cells = {(f["jurisdiction"], f["dimension"]) for f in report["findings"]}
    assert len(cells) == 3 * 12


def test_findings_controlled_vocab(report):
    for f in report["findings"]:
        assert f["finding_type"] in FINDING_TYPES
        assert f["statement_origin"] in STATEMENT_ORIGINS
    for f in report["cross_dimension_findings"]:
        assert f["pattern"] in CROSS_DIMENSION_PATTERNS


def test_findings_evidence_status_matches_cell(report):
    statuses = {f["evidence_status"] for f in report["findings"]}
    assert statuses <= {"supported", "partial", "conflicting", "missing_evidence"}
    for f in report["findings"]:
        summary = next(d for d in report["dimensions"] if d["dimension"] == f["dimension"])
        cell = summary["cases"][f["jurisdiction"]]
        assert f["evidence_status"] == cell["evidence_status"]


def test_findings_ethiopia_supported_cells(report):
    by_id = {f["finding_id"]: f for f in report["findings"]}
    t = by_id["ETHIOPIA-transparency-supported_finding"]
    assert sorted(r["evidence_id"] for r in t["evidence_refs"]) == [28, 29, 33]
    assert t["statement_origin"] == "evidence_derived"
    assert t["confidence"] == 3
    assert t["interpretation"]
    assert "ETHIOPIA-transparency-source_quality" in \
        [r["gap_id"] for r in t["research_gap_refs"]]

    i = by_id["ETHIOPIA-interoperability-supported_finding"]
    assert sorted(r["evidence_id"] for r in i["evidence_refs"]) == [26, 31]

    d = by_id["ETHIOPIA-data_localization-supported_finding"]
    assert sorted(r["evidence_id"] for r in d["evidence_refs"]) == [2, 27, 30]
    assert d["confidence"] == 4
    assert "ETHIOPIA-data_localization-temporal_coverage" in \
        [r["gap_id"] for r in d["research_gap_refs"]]


def test_findings_missing_cell_is_limitation(report):
    by_id = {f["finding_id"]: f for f in report["findings"]}
    f = by_id["EUROPEAN_UNION-transparency-evidence_limitation"]
    assert f["finding_type"] == "evidence_limitation"
    assert f["pattern"] == "insufficient_evidence"
    assert f["statement_origin"] == "corpus_limitation"
    assert f["evidence_refs"] == []
    assert "insufficient evidence" in f["statement"]
    assert "never a negative assessment" in f["statement"]
    assert f["confidence"] is None


def test_findings_missing_is_never_negative(report):
    for f in report["findings"]:
        if f["evidence_status"] == "missing_evidence":
            lowered = f["statement"].lower()
            assert "never a negative assessment" in lowered
            assert f["finding_type"] == "evidence_limitation"


def test_findings_evidence_refs_exist_and_real(report):
    db_ids = {e.evidence_id for e in Evidence.select()}
    for f in report["findings"]:
        for ref in f["evidence_refs"]:
            assert ref["evidence_id"] in db_ids
    for f in report["comparative_findings"]:
        for ref in f["evidence_refs"]:
            assert ref["evidence_id"] in db_ids


def test_findings_observation_refs_match_cell(report, committed_db):
    from src.governance.comparison import _cell_observations
    for f in report["findings"]:
        allowed = {o.observation_id
                   for o in _cell_observations(f["jurisdiction"], f["dimension"])}
        for r in f["observation_refs"]:
            assert r["observation_id"] in allowed


def test_findings_no_scores_or_rankings(report):
    for f in report["findings"] + report["comparative_findings"]:
        assert "score" not in f["statement"].lower()
        assert "rank" not in f["statement"].lower()
    for f in report["comparative_findings"]:
        if f["finding_type"] == "comparative_finding":
            assert any("not a score" in lim for lim in f["limitations"])
    assert any("scores" in lim for lim in report["limitations"])


def test_findings_interpretation_stays_separate(report):
    f = next(x for x in report["findings"]
             if x["finding_id"] == "ETHIOPIA-data_localization-supported_finding")
    assert f["interpretation"]
    # the deterministic statement must not silently absorb the assessment text
    for text in f["interpretation"]:
        assert text not in f["statement"]


# ---------------------------------------------------------------------------
# Comparative findings
# ---------------------------------------------------------------------------

def test_findings_comparative_only_for_evidenced_pairs(report):
    comps = [f for f in report["comparative_findings"]
             if f["finding_type"] == "comparative_finding"]
    assert comps
    for f in comps:
        summary = next(d for d in report["dimensions"] if d["dimension"] == f["dimension"])
        eth = summary["cases"]["Ethiopia"]
        assert eth["evidence_status"] != "missing_evidence"
        for c in f["pair"]:
            if c != "Ethiopia":
                assert summary["cases"][c]["evidence_status"] != "missing_evidence"
        assert sorted(r["evidence_id"] for r in f["evidence_refs"]) == sorted(
            f["comparison"]["ethiopia_evidence_ids"]
            + f["comparison"]["comparator_evidence_ids"])
        assert f["support_relation"] in {
            "both_supported", "ethiopia_more_supported",
            "comparator_more_supported", "broadly_similar", "conflicting"}


def test_findings_comparative_evidence_limitation(report):
    by_id = {f["finding_id"]: f for f in report["comparative_findings"]}
    for fid in ("CROSS_CASE-transparency-evidence_limitation-ETHIOPIA-EUROPEAN_UNION",
                "CROSS_CASE-transparency-evidence_limitation-ETHIOPIA-KENYA"):
        f = by_id[fid]
        assert f["finding_type"] == "evidence_limitation"
        assert f["pattern"] == "insufficient_evidence"
        assert f["statement_origin"] == "corpus_limitation"
        assert f["comparison"]["comparator_evidence_ids"] == []


def test_findings_data_localization_comparative(report):
    by_id = {f["finding_id"]: f for f in report["comparative_findings"]}
    f = by_id["CROSS_CASE-data_localization-comparative_finding-ETHIOPIA-EUROPEAN_UNION"]
    assert f["support_relation"] == "ethiopia_more_supported"
    assert f["comparison"]["ethiopia_evidence_ids"] == [2, 27, 30]
    assert f["comparison"]["comparator_evidence_ids"] == [32]
    assert sorted(f["pair"]) == ["Ethiopia", "European Union"]
    assert f["jurisdiction"] == "Cross-case"
    assert f["comparison"]["cross_case_note"] in {
        "similar_pattern", "different_pattern", "insufficient_evidence",
        "not_comparable"}


def test_findings_comparative_pair_sorted_and_unique(report):
    ids = [f["finding_id"] for f in report["comparative_findings"]]
    assert len(ids) == len(set(ids))
    for f in report["comparative_findings"]:
        assert "ETHIOPIA" in f["finding_id"]


# ---------------------------------------------------------------------------
# Cross-dimension findings
# ---------------------------------------------------------------------------

def test_findings_cross_dimension_shared_source(report):
    shared = [f for f in report["cross_dimension_findings"]
              if f["pattern"] == "shared_source_pattern"]
    assert shared
    for f in shared:
        assert len(f["dimensions"]) >= 2
        assert f["evidence_ids"]
        assert "not a causal link" in f["statement"]


def test_findings_cross_dimension_recurring_limitation(report):
    rec = [f for f in report["cross_dimension_findings"]
           if f["pattern"] == "recurring_evidence_limitation"]
    assert rec
    f = rec[0]
    assert f["scope"] == "Ethiopia"
    assert f["dimensions"]
    assert "normative" in f["statement"]


def test_findings_cross_dimension_no_causal(report):
    nc = [f for f in report["cross_dimension_findings"]
          if f["pattern"] == "no_causal_inference"]
    assert len(nc) == 1
    assert "does not" in nc[0]["statement"]


def test_findings_cross_dimension_novel_vocab(report):
    ids = [f["finding_id"] for f in report["cross_dimension_findings"]]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Ethiopia primary-case synthesis
# ---------------------------------------------------------------------------

def test_findings_ethiopia_synthesis_shape(report):
    eth = report["ethiopia_synthesis"]
    assert eth["case"] == "Ethiopia"
    assert sum(eth["status_counts"].values()) == 12
    assert len(eth["primary_finding_ids"]) == 12
    assert eth["confidence_average"] == 4
    expected = sorted(f["finding_id"] for f in report["findings"]
                      if f["jurisdiction"] == "Ethiopia")
    assert eth["primary_finding_ids"] == expected


# ---------------------------------------------------------------------------
# Resolved / remaining research gaps
# ---------------------------------------------------------------------------

def test_findings_resolved_gaps_recorded(report, gap_ids):
    resolved = report["resolved_research_gaps"]
    assert len(resolved) == 5
    for rec in resolved:
        assert rec["gap_id"] not in gap_ids
        assert rec["resolving_evidence_ids"]
        assert rec["category"]


def test_findings_resolved_gaps_evidence_membership(report, committed_db):
    from src.governance.matrix import _jurisdiction_evidence_ids
    for rec in report["resolved_research_gaps"]:
        allowed = _jurisdiction_evidence_ids(rec["jurisdiction"], rec["dimension"])
        for eid in rec["resolving_evidence_ids"]:
            assert eid in allowed


def test_findings_remaining_gaps_match_discover_gaps(report, gap_ids):
    remaining_ids = [g["gap_id"] for g in report["remaining_research_gaps"]]
    assert set(remaining_ids) == gap_ids
    assert len(remaining_ids) == len(set(remaining_ids))


def test_findings_remaining_gap_sort(report):
    ids = [g["gap_id"] for g in report["remaining_research_gaps"]]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def test_findings_case_filter(committed_db):
    r = build_findings_report(case="Ethiopia")
    assert len(r["findings"]) == 12
    assert all(f["jurisdiction"] == "Ethiopia" for f in r["findings"])
    assert all("ETHIOPIA" in f["finding_id"] for f in r["comparative_findings"])


def test_findings_dimension_filter(committed_db):
    r = build_findings_report(dimension="data_localization")
    assert len(r["findings"]) == 3
    assert all(f["dimension"] == "data_localization" for f in r["findings"])
    assert all(f["dimension"] == "data_localization"
               for f in r["comparative_findings"])
    assert all(c["dimension"] == "data_localization"
               for c in r["evidence_coverage"])


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def test_findings_markdown_deterministic(report):
    md1 = findings_to_markdown(report)
    md2 = findings_to_markdown(build_findings_report())
    assert md1 == md2
    assert "# Evidence Findings Synthesis" in md1


# ---------------------------------------------------------------------------
# Validation integrity
# ---------------------------------------------------------------------------

def test_findings_validation_passes(report):
    model = validate_findings(report)
    assert model.report_type == "evidence_findings_synthesis"


def test_findings_validation_schema_rejects_bad_type(report):
    bad = copy.deepcopy(report)
    bad["findings"][0]["finding_type"] = "invented_type"
    with pytest.raises(ValidationError):
        validate_findings(bad)


def test_findings_validation_schema_rejects_bad_dimension(report):
    bad = copy.deepcopy(report)
    bad["findings"][0]["dimension"] = "not_a_governance_dimension"
    with pytest.raises(ValidationError):
        validate_findings(bad)


def test_findings_validation_rejects_orphan_evidence(report):
    bad = copy.deepcopy(report)
    f = bad["findings"][0]
    f["evidence_refs"][0]["evidence_id"] = 9999
    with pytest.raises(ValueError):
        validate_findings(bad)


def test_findings_validation_rejects_unresolved_resolved_gap(report, gap_ids):
    bad = copy.deepcopy(report)
    live = sorted(gap_ids)[0]
    bad["resolved_research_gaps"].append({
        "gap_id": live,
        "category": "evidence_coverage",
        "jurisdiction": "Ethiopia",
        "dimension": "transparency",
        "resolving_evidence_ids": [28],
        "resolution_note": "bogus",
    })
    with pytest.raises(ValueError):
        validate_findings(bad)


def test_findings_validation_rejects_duplicate_finding_ids(report):
    bad = copy.deepcopy(report)
    bad["findings"].append(dict(bad["findings"][0]))
    with pytest.raises(ValueError):
        validate_findings(bad)


def test_findings_validation_rejects_duplicate_remaining_gap(report, gap_ids):
    bad = copy.deepcopy(report)
    g = dict(report["remaining_research_gaps"][0])
    bad["remaining_research_gaps"].append(g)
    with pytest.raises(ValueError):
        validate_findings(bad)


def test_findings_validation_rejects_duplicate_cross_dim(report):
    bad = copy.deepcopy(report)
    bad["cross_dimension_findings"].append(
        dict(report["cross_dimension_findings"][0]))
    with pytest.raises(ValueError):
        validate_findings(bad)


def test_findings_validation_rejects_bad_corpus_digest(report):
    bad = copy.deepcopy(report)
    bad["corpus_state"]["corpus_digest"] = "0" * 64
    with pytest.raises(ValueError):
        validate_findings(bad)


# ---------------------------------------------------------------------------
# Regression: Steps 6-10 are untouched
# ---------------------------------------------------------------------------

def test_findings_regression_step10_corpus(committed_db):
    assert Source.select().count() == 17
    assert Evidence.select().count() == 33
    gap_ids = {g["gap_id"] for g in discover_gaps()}
    for resolved in ["ETHIOPIA-transparency-evidence_coverage",
                     "ETHIOPIA-interoperability-evidence_coverage",
                     "ETHIOPIA-data_localization-source_diversity",
                     "ETHIOPIA-data_localization-methodological_limitation",
                     "EUROPEAN_UNION-data_localization-evidence_coverage"]:
        assert resolved not in gap_ids


def test_findings_regression_comparative_data_localization(committed_db):
    cmp_report = comparative_analysis(["Ethiopia", "European Union"])
    dims = {d["dimension"]: d for d in cmp_report["dimensions"]}
    eth = dims["data_localization"]["cases"]["Ethiopia"]
    eu = dims["data_localization"]["cases"]["European Union"]
    assert eth["evidence_status"] == "supported"
    assert eu["evidence_status"] == "partial"
    assert eu["evidence"][0]["evidence_id"] == 32


def test_findings_matching_committed_manifest(report):
    cs = report["corpus_state"]
    with open(os.path.join(DATA, "evidence", "corpus_manifest.json"),
              encoding="utf-8") as f:
        manifest = json.load(f)
    recorded = 0
    for entry in manifest:
        with open(os.path.join(DATA, "evidence", entry["file"]),
                  encoding="utf-8") as c:
            recorded += len(json.load(c))
    assert recorded == 33
    assert cs["evidence"] == recorded