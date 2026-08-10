import json

import pytest

from src.cli import main


def test_cli_init(tmp_path, capsys, monkeypatch, eds_test_db):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    out = capsys.readouterr().out
    assert "Database initialized" in out


def test_cli_source_list_empty(capsys, eds_test_db):
    main(["source", "list"])
    assert capsys.readouterr().out.strip() == ""


def test_cli_source_add_and_list(capsys, eds_test_db):
    main(["source", "add", "--title", "CLI Law", "--type", "law",
          "--pub", "Agency", "--date", "2024-01-01", "--jur", "Ethiopia",
          "--url", "https://example.com/cli-law"])
    out = capsys.readouterr().out
    assert "Added source" in out

    main(["source", "list"])
    out = capsys.readouterr().out
    assert "CLI Law" in out


def test_cli_compare_empty_reports_missing(capsys, eds_test_db):
    main(["compare", "--j1", "X", "--j2", "Y"])
    data = json.loads(capsys.readouterr().out)
    assert data["comparison"] == {"jurisdiction_a": "X", "jurisdiction_b": "Y"}
    for dim in data["dimensions"]:
        assert dim["X"]["status"] == "missing_evidence"
        assert dim["Y"]["status"] == "missing_evidence"


def test_cli_research_status(capsys, eds_test_db):
    main(["research-status"])
    data = json.loads(capsys.readouterr().out)
    assert data["report_type"] == "research_status"
    assert "sources" in data
    assert "governance" in data


def test_cli_unknown_command_raises(capsys, eds_test_db):
    with pytest.raises(SystemExit):
        main(["bogus-command"])
    err = capsys.readouterr().err
    assert "invalid choice" in err


def test_cli_relation_create_and_list(capsys, eds_test_db):
    from src.evidence.collection import add_source
    from src.evidence.ingestion import ingest_evidence

    s = add_source({
        "title": "CLI source", "source_type": "law",
        "publisher_or_author": "Agency", "publication_date": "2024-01-01",
        "jurisdiction": "Ethiopia", "url": "https://example.com/cli-rel",
    })
    e1 = ingest_evidence({
        "title": "Ev1", "source_type": "law", "publisher_or_author": "Agency",
        "publication_date": "2024-01-01", "country_or_jurisdiction": "Ethiopia",
        "domain_theme": "data_governance", "claim": "c", "evidence_summary": "s",
        "reliability_level": 3, "evidence_strength": 3,
    }, s.source_id)
    e2 = ingest_evidence({
        "title": "Ev2", "source_type": "law", "publisher_or_author": "Agency",
        "publication_date": "2024-01-01", "country_or_jurisdiction": "Ethiopia",
        "domain_theme": "data_governance", "claim": "c", "evidence_summary": "s",
        "reliability_level": 3, "evidence_strength": 3,
    }, s.source_id)

    main(["relation", "--evidence-a", str(e1.evidence_id),
          "--evidence-b", str(e2.evidence_id), "--type", "contradicts", "--notes", "x"])
    assert "Created relation" in capsys.readouterr().out

    main(["relation", "--evidence-a", str(e1.evidence_id), "--list"])
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 1
    assert data[0]["related_evidence_id"] == e2.evidence_id
    assert data[0]["relation_type"] == "contradicts"


def test_cli_relation_requires_arguments(capsys, eds_test_db):
    with pytest.raises(SystemExit):
        main(["relation", "--evidence-a", "1"])
    assert "required" in capsys.readouterr().out


def test_cli_research_matrix(capsys, eds_test_db):
    main(["research-matrix", "--jurisdiction", "Ethiopia"])
    data = json.loads(capsys.readouterr().out)
    assert data["report_type"] == "research_matrix"
    assert len(data["matrix"]) == 12
    assert all(d["status"] in ("supported", "partial", "missing_evidence")
               for d in data["matrix"])


def test_cli_coverage_matrix(capsys, eds_test_db):
    from src.evidence.collection import add_source
    from src.evidence.ingestion import ingest_evidence

    s = add_source({
        "title": "CLI source", "source_type": "law",
        "publisher_or_author": "Agency", "publication_date": "2024-01-01",
        "jurisdiction": "Ethiopia", "url": "https://example.com/cli-cov",
    })
    ingest_evidence({
        "title": "Ev1", "source_type": "law", "publisher_or_author": "Agency",
        "publication_date": "2024-01-01", "country_or_jurisdiction": "Ethiopia",
        "domain_theme": "consent", "claim": "c", "evidence_summary": "s",
        "reliability_level": 3, "evidence_strength": 3,
    }, s.source_id)

    main(["coverage-matrix", "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert data[0]["governance_dimension"] == "data_governance"
    assert all(r["status"] in ("supported", "partial", "missing_evidence") for r in data)


def test_cli_baseline(capsys, eds_test_db):
    main(["baseline", "--j1", "Ethiopia", "--j2", "Kenya"])
    data = json.loads(capsys.readouterr().out)
    assert data["report_type"] == "comparative_baseline"
    notes = {d["comparison_note"] for d in data["dimensions"]}
    assert notes <= {"similar_pattern", "different_pattern",
                     "insufficient_evidence", "not_comparable"}
