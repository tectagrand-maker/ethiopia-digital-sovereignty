"""Step 9: research gap prioritization & evidence expansion framework tests.

Covers gap discovery, classification, prioritization determinism and rules,
research-action generation, source recommendations, missing/conflicting/low-
confidence evidence, comparative and cross-case gaps, case-study integration,
provenance validation, orphan references, deterministic serialization, CLI, and
regression against Steps 6-8.
"""

import json

import pytest
from pydantic import ValidationError

from src.evidence.models import GOVERNANCE_DIMENSIONS
from src.evidence.ingestion import ingest_evidence
from src.evidence.collection import add_source
from src.governance.analysis import (
    create_observation, create_evidence_relation,
)
from src.governance.comparison import comparative_analysis
from src.governance.status import research_status_report
from src.governance.casestudy import case_study_dossier, validate_dossier
from src.governance.research_gaps import (
    discover_gaps, research_plan, validate_plan, plan_to_json, plan_to_markdown,
    evidence_expansion_requirements, validate_evidence_record,
    gaps_for_jurisdiction,
)
from src.cli import main


def _source(jurisdiction="Alpha", url=None, **extra):
    url = url or ("https://example.com/rg-" + jurisdiction
                  + str(abs(hash(jurisdiction)) % 100000))
    data = {
        "title": "Gov source " + url,
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "jurisdiction": jurisdiction,
        "url": url,
    }
    data.update(extra)
    return add_source(data)


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
        "reliability_level": 4,
        "evidence_strength": 4,
        "evidence_basis": "normative",
        "locator_type": "page",
        "locator_value": "12",
        "citation": "CIT " + s.url,
    }
    data.update(overrides or {})
    return ingest_evidence(data, s.source_id)


def _obs_data(jurisdiction="Alpha", dimension="data_governance", confidence=4,
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


def _gap_by_id(gaps, gap_id):
    return next(g for g in gaps if g["gap_id"] == gap_id)


# ---------------------------------------------------------------------------
# Gap discovery
# ---------------------------------------------------------------------------

def test_empty_db_no_gaps():
    assert discover_gaps() == []


def test_evidence_coverage_gap_on_missing_dimension():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-transparency-evidence_coverage")
    assert g["category"] == "evidence_coverage"
    assert g["evidence_status"] == "missing_evidence"
    assert g["evidence_available"] == []
    assert g["scope"] == "comparator_specific"  # case is not Ethiopia


def test_source_diversity_gap_single_source():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-source_diversity")
    assert g["category"] == "source_diversity"
    assert g["evidence_status"] == "partial"
    assert g["evidence_available"] != []


def test_confidence_limitation_gap():
    s = _source()
    e = _evidence(s, {"domain_theme": "consent"})
    create_observation(_obs_data(dimension="consent_individual_agency", confidence=2),
                       [e.evidence_id])
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-confidence_limitation")
    assert g["category"] == "confidence_limitation"
    assert g["confidence"] == 2


def test_conflicting_evidence_gap():
    s = _source()
    e1 = _evidence(s, {"title": "EvCf1"})
    e2 = _evidence(s, {"title": "EvCf2"})
    create_evidence_relation(e1.evidence_id, e2.evidence_id, "contradicts", "note")
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-data_governance-conflicting_evidence")
    assert g["category"] == "conflicting_evidence"
    assert "ev" in g["reason"] and "vs" in g["reason"]


def test_temporal_coverage_gap_undated_evidence():
    s = _source()
    _evidence(s, {"domain_theme": "consent", "publication_date": None})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-temporal_coverage")
    assert g["category"] == "temporal_coverage"


def test_methodological_limitation_gap_all_normative():
    s = _source()
    _evidence(s, {"domain_theme": "consent", "evidence_basis": "normative"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-methodological_limitation")
    assert g["category"] == "methodological_limitation"
    assert "normative" in g["reason"]


def test_methodological_limitation_gap_no_observation():
    s = _source()
    _evidence(s, {"domain_theme": "consent", "evidence_basis": "implementation"})
    gaps = discover_gaps()
    assert _gap_by_id(gaps, "ALPHA-consent_individual_agency-methodological_limitation")


def test_source_quality_gap_low_strength():
    s = _source()
    _evidence(s, {"domain_theme": "consent", "evidence_strength": 2,
                  "reliability_level": 2})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-source_quality")
    assert "low evidence_strength" in g["reason"]
    assert "low reliability_level" in g["reason"]


def test_source_quality_gap_missing_locator():
    s = _source()
    _evidence(s, {"domain_theme": "consent", "locator_type": None,
                  "locator_value": None})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ALPHA-consent_individual_agency-source_quality")
    assert "missing locator" in g["reason"]


# ---------------------------------------------------------------------------
# Comparative and cross-case gaps
# ---------------------------------------------------------------------------

def test_comparative_gap_comparator_missing():
    s_eth = _source(jurisdiction="Ethiopia", url="https://example.com/rg-e1")
    s_ken = _source(jurisdiction="Kenya", url="https://example.com/rg-e2")
    _evidence(s_eth, {"domain_theme": "consent"})
    _evidence(s_ken, {"domain_theme": "data_governance"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "KENYA-consent_individual_agency-comparative_coverage")
    assert g["category"] == "comparative_coverage"
    assert g["scope"] == "comparative_coverage"
    assert g["jurisdiction"] == "Kenya"
    assert g["comparator_context"]["primary_case"] == "Ethiopia"
    assert g["comparator_context"]["comparator"] == "Kenya"


def test_comparative_gap_primary_missing_comparator_has():
    s_eth = _source(jurisdiction="Ethiopia", url="https://example.com/rg-e3")
    s_ken = _source(jurisdiction="Kenya", url="https://example.com/rg-e4")
    _evidence(s_eth, {"domain_theme": "data_governance"})
    _evidence(s_ken, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ETHIOPIA-consent_individual_agency-comparative_coverage")
    assert g["scope"] == "comparative_coverage"
    assert g["jurisdiction"] == "Ethiopia"


def test_cross_case_gap():
    s_eth = _source(jurisdiction="Ethiopia", url="https://example.com/rg-e5")
    s_ken = _source(jurisdiction="Kenya", url="https://example.com/rg-e6")
    _evidence(s_eth, {"domain_theme": "consent"})
    _evidence(s_ken, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "CROSS-CASE-transparency-comparative_coverage")
    assert g["scope"] == "cross_case"
    assert g["jurisdiction"] == "Cross-case"
    assert "Ethiopia" in g["affected_cases"] and "Kenya" in g["affected_cases"]


def test_scope_classification():
    s_eth = _source(jurisdiction="Ethiopia", url="https://example.com/rg-e7")
    s_ken = _source(jurisdiction="Kenya", url="https://example.com/rg-e8")
    _evidence(s_eth, {"domain_theme": "consent"})
    _evidence(s_ken, {"domain_theme": "data_governance"})
    gaps = discover_gaps()
    scopes = {g["gap_id"]: g["scope"] for g in gaps}
    assert scopes["ETHIOPIA-consent_individual_agency-source_diversity"] == "ethiopia_specific"
    assert scopes["KENYA-data_governance-source_diversity"] == "comparator_specific"


# ---------------------------------------------------------------------------
# Prioritization
# ---------------------------------------------------------------------------

def test_prioritization_deterministic():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-p1")
    _evidence(s, {"domain_theme": "consent"})
    first = discover_gaps()
    second = discover_gaps()
    assert first == second
    assert len(first) > 0
    ids = [g["gap_id"] for g in first]
    assert ids == [g["gap_id"] for g in
                   sorted(first, key=lambda g: (-g["priority_score"], g["gap_id"]))]


def test_priority_rule_high():
    s_eth = _source(jurisdiction="Ethiopia", url="https://example.com/rg-p2")
    s_ken = _source(jurisdiction="Kenya", url="https://example.com/rg-p3")
    _evidence(s_eth, {"domain_theme": "data_governance"})
    _evidence(s_ken, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ETHIOPIA-consent_individual_agency-evidence_coverage")
    assert g["priority_level"] == "high"
    assert g["priority_score"] == 8
    factors = {f["factor"]: f["points"] for f in g["priority_factors"]}
    assert factors["dimension_importance"] == 3
    assert factors["severity"] == 3
    assert factors["primary_case"] == 1
    assert factors["comparative_importance"] == 1


def test_priority_rule_low():
    s = _source(jurisdiction="Zulu", url="https://example.com/rg-p4")
    _evidence(s, {"domain_theme": "consent"})
    gaps = discover_gaps()
    g = _gap_by_id(gaps, "ZULU-transparency-evidence_coverage")
    assert g["priority_level"] == "low"
    assert g["priority_score"] == 4
    assert g["priority_rationale"].endswith("(thresholds: high>=7, medium>=5, else low).")


def test_priority_thresholds_documented_in_plan():
    plan = research_plan()
    meth = plan["methodology"]
    assert meth["priority_formula"].startswith("score = dimension_importance + severity + breadth")
    assert meth["priority_thresholds"] == {"high": 7, "medium": 5}
    assert "not governance scores" in meth["disclaimer"]


# ---------------------------------------------------------------------------
# Research actions and source strategy
# ---------------------------------------------------------------------------

def test_research_action_fields():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    action = next(a for a in plan["prioritized_actions"]
                  if a["gap_id"] == "ALPHA-consent_individual_agency-source_diversity")
    assert action["jurisdiction"] == "Alpha"
    assert action["dimension"] == "consent_individual_agency"
    assert action["category"] == "source_diversity"
    assert action["priority_level"] in ("high", "medium", "low")
    assert action["recommended_source_types"]
    assert action["research_question"].endswith("?")
    assert action["expected_analytical_value"]
    assert action["dependencies"]
    assert action["provenance_requirements"]
    assert action["reason"]
    assert action["evidence_available"]


def test_recommended_source_types_are_controlled():
    from src.evidence.models import SourceType
    valid = {e.value for e in SourceType}
    for cat, types in research_plan()["recommended_source_types"].items():
        assert set(types) <= valid


def test_recommended_catalog_sources():
    _source(url="https://example.com/rg-c1", research_domains="consent")
    s = _source(url="https://example.com/rg-c2")
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    action = next(a for a in plan["prioritized_actions"]
                  if a["dimension"] == "consent_individual_agency")
    assert action["recommended_catalog_sources"] != []


def test_evidence_expansion_requirements():
    req = evidence_expansion_requirements()
    assert "title" in req["required_record_fields"]
    assert "claim" in req["required_record_fields"]
    assert req["provenance_steps"]
    assert "Never insert unverified research material" in req["note"]
    assert "ingestion" in req["ingest_route"]


def test_validate_evidence_record_valid_and_invalid():
    good = {
        "title": "New law", "source_type": "law",
        "publisher_or_author": "Agency", "publication_date": "2024-01-01",
        "country_or_jurisdiction": "Ethiopia", "domain_theme": "consent",
        "claim": "c", "evidence_summary": "s",
        "reliability_level": 5, "evidence_strength": 5,
        "evidence_basis": "normative", "locator_type": "section",
        "locator_value": "1", "citation": "cite",
    }
    assert validate_evidence_record(good)["valid"] is True
    bad = dict(good)
    bad.pop("claim")
    bad["domain_theme"] = "not_a_domain"
    result = validate_evidence_record(bad)
    assert result["valid"] is False
    assert "claim" in result["missing_required"]
    assert result["validation_errors"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_plan_accepts():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-v1")
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    model = validate_plan(plan)
    assert model.report_type == "research_gap_plan"
    assert len(model.gaps) == len(model.prioritized_actions)


def test_validate_plan_orphan_evidence_ref():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"][0]["evidence_available"] = [999999]
    with pytest.raises(ValueError, match="[Oo]rphan"):
        validate_plan(plan)


def test_validate_plan_jurisdiction_mismatch():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"][0]["jurisdiction"] = "Phantom"
    with pytest.raises(ValueError, match="jurisdiction"):
        validate_plan(plan)


def test_validate_plan_evidence_jurisdiction_mismatch():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/rg-v2")
    s_b = _source(jurisdiction="Beta", url="https://example.com/rg-v3")
    _evidence(s_a, {"domain_theme": "consent"})
    _evidence(s_b, {"domain_theme": "data_governance"})
    plan = research_plan()
    gap = next(g for g in plan["gaps"] if g["gap_id"] == "ALPHA-consent_individual_agency-source_diversity")
    gap["jurisdiction"] = "Beta"
    with pytest.raises(ValueError, match="does not match"):
        validate_plan(plan)


def test_validate_plan_invalid_category_pydantic():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"][0]["category"] = "totally_new_category"
    with pytest.raises(ValidationError):
        validate_plan(plan)


def test_validate_plan_invalid_dimension_pydantic():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"][0]["dimension"] = "not_a_dimension"
    with pytest.raises(ValidationError):
        validate_plan(plan)


def test_validate_plan_duplicate_gap_ids():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"].append(dict(plan["gaps"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_plan(plan)


def test_validate_plan_priority_order():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["gaps"].reverse()
    with pytest.raises(ValueError, match="priority order"):
        validate_plan(plan)


def test_validate_plan_action_mismatch():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["prioritized_actions"][0]["gap_id"] = "SOMETHING-ELSE"
    with pytest.raises(ValueError, match="gap_id"):
        validate_plan(plan)


def test_validate_plan_action_missing_question():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    plan = research_plan()
    plan["prioritized_actions"][0]["research_question"] = "not a question"
    with pytest.raises(ValidationError):
        validate_plan(plan)


# ---------------------------------------------------------------------------
# Serialization and filtering
# ---------------------------------------------------------------------------

def test_plan_deterministic_json():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    assert plan_to_json(research_plan()) == plan_to_json(research_plan())


def test_plan_markdown_renders():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    md = plan_to_markdown(research_plan())
    assert "# Research Gap Prioritization Plan" in md
    assert "## Gap inventory" in md
    assert "## Prioritized research actions" in md
    assert "## Limitations" in md


def test_plan_filters():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-f1")
    s2 = _source(jurisdiction="Kenya", url="https://example.com/rg-f2")
    _evidence(s, {"domain_theme": "consent"})
    _evidence(s2, {"domain_theme": "consent"})
    full = research_plan()
    by_case = research_plan(case="Ethiopia")
    assert all("Ethiopia" == g["jurisdiction"] or "Ethiopia" in g["affected_cases"]
               for g in by_case["gaps"])
    assert len(by_case["gaps"]) < len(full["gaps"])
    by_dim = research_plan(dimension="consent_individual_agency")
    assert all(g["dimension"] == "consent_individual_agency" for g in by_dim["gaps"])
    high_only = research_plan(min_priority="high")
    assert all(g["priority_level"] == "high" for g in high_only["gaps"])


def test_plan_min_priority_invalid():
    s = _source()
    _evidence(s)
    with pytest.raises(ValueError, match="min_priority"):
        research_plan(min_priority="critical")


# ---------------------------------------------------------------------------
# Case-study integration (Step 8)
# ---------------------------------------------------------------------------

def test_casestudy_dossier_gap_references():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-cs1")
    _evidence(s, {"domain_theme": "consent"})
    dossier = case_study_dossier("Ethiopia")
    model = validate_dossier(dossier)
    assert model.gap_references
    ref = model.gap_references[0]
    assert ref.gap_id
    assert ref.category
    assert ref.priority_level in ("high", "medium", "low")
    # references must not duplicate the full gap definitions
    assert "reason" not in ref.model_dump()
    assert "research_question" not in ref.model_dump()


def test_gaps_for_jurisdiction_sorted():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-cs2")
    _evidence(s, {"domain_theme": "consent"})
    refs = gaps_for_jurisdiction("Ethiopia")
    ids = [r["gap_id"] for r in refs]
    assert ids == sorted(ids)
    assert all(r["category"] in {"evidence_coverage", "source_diversity",
                                 "source_quality", "temporal_coverage",
                                 "confidence_limitation",
                                 "methodological_limitation",
                                 "conflicting_evidence",
                                 "comparative_coverage"} for r in refs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_research_gaps_json(capsys, eds_test_db):
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    main(["research-gaps"])
    data = json.loads(capsys.readouterr().out)
    assert data["report_type"] == "research_gap_plan"
    assert data["gaps"]
    assert data["prioritized_actions"]


def test_cli_research_gaps_markdown(capsys, eds_test_db):
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    main(["research-gaps", "--format", "markdown"])
    assert "# Research Gap Prioritization Plan" in capsys.readouterr().out


def test_cli_research_gaps_validate(capsys, eds_test_db):
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-cli1")
    _evidence(s, {"domain_theme": "consent"})
    main(["research-gaps", "--case", "Ethiopia", "--validate"])
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == 1


def test_cli_research_gaps_filters(capsys, eds_test_db):
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    main(["research-gaps", "--dimension", "transparency", "--priority", "high",
          "--format", "json"])
    data = json.loads(capsys.readouterr().out)
    assert all(g["dimension"] == "transparency" for g in data["gaps"])
    assert all(g["priority_level"] == "high" for g in data["gaps"])


# ---------------------------------------------------------------------------
# Regression against Steps 6-8
# ---------------------------------------------------------------------------

def test_regression_comparative_analysis_still_works():
    s_a = _source(jurisdiction="Alpha", url="https://example.com/rg-r1")
    s_b = _source(jurisdiction="Beta", url="https://example.com/rg-r2")
    _evidence(s_a, {"domain_theme": "consent"})
    _evidence(s_b, {"domain_theme": "consent"})
    report = comparative_analysis(["Alpha", "Beta"])
    assert [c["jurisdiction"] for c in report["cases"]] == ["Alpha", "Beta"]


def test_regression_research_status_still_works():
    s = _source()
    _evidence(s, {"domain_theme": "consent"})
    report = research_status_report()
    assert report["report_type"] == "research_status"


def test_regression_case_study_dossier_still_validates():
    s = _source(jurisdiction="Ethiopia", url="https://example.com/rg-r3")
    e = _evidence(s, {"domain_theme": "consent"})
    create_observation(_obs_data(jurisdiction="Ethiopia",
                                 dimension="consent_individual_agency"),
                       [e.evidence_id])
    validate_dossier(case_study_dossier("Ethiopia"))
