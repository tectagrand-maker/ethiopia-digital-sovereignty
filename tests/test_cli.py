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
