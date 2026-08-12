import argparse
import json
import sys
import urllib.error

from src.evidence.models import (
    initialize_db, Evidence, Source, GovernanceObservation, DataStatus,
)
from src.evidence.ingestion import import_from_json, import_from_csv
from src.evidence.extraction import extract_text
from src.evidence.collection import (
    add_source, get_source, list_sources, update_source_status,
    acquire_source, save_raw_source, verify_raw_source, import_source_manifest,
)
from src.governance.analysis import (
    create_observation, get_comparative_data,
    comparison_to_json, comparison_to_csv,
    comparative_baseline, create_evidence_relation, get_evidence_relations,
)
from src.governance.status import research_status_report, report_to_json
from src.governance.matrix import (
    coverage_matrix, research_matrix, matrix_to_csv,
)
from src.governance.comparison import (
    comparative_analysis, analysis_to_json, analysis_to_csv, validate_report,
)
from src.governance.casestudy import (
    case_study_dossier, validate_dossier, dossier_to_json, dossier_to_markdown,
)
from src.governance.research_gaps import (
    research_plan, validate_plan, plan_to_json, plan_to_markdown,
)
from src.governance.findings import (
    build_findings_report, validate_findings,
    findings_to_json, findings_to_markdown,
)
from src.governance.narrative import (
    case_study_narrative, validate_narrative,
    narrative_to_json, narrative_to_markdown,
)
from src.governance.academic import (
    build_academic_draft, validate_academic_draft,
    academic_to_json, academic_to_markdown,
)


def _source_row(s):
    return f"{s.source_id}: {s.title} [{s.jurisdiction}] ({s.status})"


def _evidence_row(e):
    return (f"{e.evidence_id}: {e.title} "
            f"(source={e.source.source_id}, status={e.data_status})")


def _print(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            print(data)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Ethiopia Digital Sovereignty research CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize database")

    # ---- source ----
    source_parser = subparsers.add_parser("source", help="Source registry management")
    source_sub = source_parser.add_subparsers(dest="subcommand")

    add_src = source_sub.add_parser("add", help="Add a source")
    add_src.add_argument("--title", required=True)
    add_src.add_argument("--type", required=True)
    add_src.add_argument("--pub", required=True)
    add_src.add_argument("--jur", required=True)
    add_src.add_argument("--date", default=None)
    add_src.add_argument("--url", default=None)
    add_src.add_argument("--group", default="ethiopia", help="ethiopia|comparative|international")
    add_src.add_argument("--status", default=None)

    src_list = source_sub.add_parser("list", help="List sources")
    src_list.add_argument("--status", default=None)
    src_list.add_argument("--group", default=None)

    src_show = source_sub.add_parser("show", help="Show a source")
    src_show.add_argument("--id", required=True, type=int)

    src_status = source_sub.add_parser("status", help="Update source status")
    src_status.add_argument("--id", required=True, type=int)
    src_status.add_argument("--status", required=True)

    src_import = source_sub.add_parser("import", help="Import source registry manifest (JSON)")
    src_import.add_argument("--file", required=True)

    src_acquire = source_sub.add_parser("acquire", help="Download a selected source to data/raw/<id>/")
    src_acquire.add_argument("--id", required=True, type=int)

    src_verify = source_sub.add_parser("verify", help="Verify raw source SHA-256 integrity")
    src_verify.add_argument("--id", required=True, type=int)

    # ---- evidence ----
    evidence_parser = subparsers.add_parser("evidence", help="Evidence management")
    ev_sub = evidence_parser.add_subparsers(dest="subcommand")

    ev_list = ev_sub.add_parser("list", help="List evidence")
    ev_list.add_argument("--source-id", default=None, type=int)

    ev_show = ev_sub.add_parser("show", help="Show evidence with full provenance")
    ev_show.add_argument("--id", required=True, type=int)

    ev_sub.add_parser("init", help="Initialize the evidence database (alias for init)")

    ingest_parser = subparsers.add_parser("ingest", help="Import evidence (JSON or CSV) for a source")
    ingest_parser.add_argument("--type", choices=["json", "csv"], required=True)
    ingest_parser.add_argument("--file", required=True)
    ingest_parser.add_argument("--source-id", required=True, type=int)

    # ---- governance ----
    obs_parser = subparsers.add_parser("observation", help="Create a governance observation")
    obs_parser.add_argument("--jurisdiction", required=True)
    obs_parser.add_argument("--system", required=True)
    obs_parser.add_argument("--dimension", required=True)
    obs_parser.add_argument("--indicator", required=True)
    obs_parser.add_argument("--observed-evidence", required=True)
    obs_parser.add_argument("--assessment", default=None)
    obs_parser.add_argument("--confidence", default=None, type=int)
    obs_parser.add_argument("--notes", default=None)
    obs_parser.add_argument("--evidence-ids", default="", help="comma-separated evidence ids")

    # ---- compare ----
    compare_parser = subparsers.add_parser("compare", help="Compare two jurisdictions")
    compare_parser.add_argument("--j1", required=True)
    compare_parser.add_argument("--j2", required=True)
    compare_parser.add_argument("--format", choices=["json", "csv"], default="json")

    # ---- extract ----
    extract_parser = subparsers.add_parser("extract", help="Extract text from a raw source file")
    extract_parser.add_argument("--file", required=True)
    extract_parser.add_argument("--source-id", default=None, type=int)
    extract_parser.add_argument("--json", action="store_true", help="Print structured extraction metadata")

    # ---- research-status ----
    subparsers.add_parser("research-status", help="Research coverage report (JSON)")

    # ---- research-matrix ----
    matrix_parser = subparsers.add_parser("research-matrix", help="Ethiopia governance evidence matrix")
    matrix_parser.add_argument("--jurisdiction", default="Ethiopia")
    matrix_parser.add_argument("--format", choices=["json", "csv"], default="json")

    # ---- coverage-matrix ----
    cov_parser = subparsers.add_parser("coverage-matrix", help="Evidence coverage matrix (jurisdiction x dimension)")
    cov_parser.add_argument("--format", choices=["json", "csv"], default="json")

    # ---- baseline ----
    baseline_parser = subparsers.add_parser("baseline", help="Comparative baseline (methodological, not a ranking)")
    baseline_parser.add_argument("--j1", required=True)
    baseline_parser.add_argument("--j2", required=True)
    baseline_parser.add_argument("--format", choices=["json", "csv"], default="json")

    # ---- relation ----
    rel_parser = subparsers.add_parser("relation", help="Record a relation between two evidence records")
    rel_parser.add_argument("--evidence-a", required=True, type=int)
    rel_parser.add_argument("--evidence-b", type=int)
    rel_parser.add_argument("--type", help="supports|qualifies|contradicts|contextualizes")
    rel_parser.add_argument("--notes", default=None)
    rel_parser.add_argument("--list", action="store_true", help="List relations for --evidence-a")

    # ---- comparative ----
    comp_parser = subparsers.add_parser(
        "comparative",
        help="Comparative governance analysis (multi-case, fully traceable)",
    )
    comp_parser.add_argument(
        "--cases", default="",
        help="Comma-separated jurisdictions (default: all available cases)",
    )
    comp_parser.add_argument("--format", choices=["json", "csv"], default="json")
    comp_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the report against the output schema before printing",
    )

    # ---- case-study ----
    case_parser = subparsers.add_parser(
        "case-study",
        help="Evidence-backed case-study dossier for a jurisdiction (Step 8)",
    )
    case_parser.add_argument(
        "--case", required=True,
        help="Jurisdiction to build the dossier for (e.g. Ethiopia)",
    )
    case_parser.add_argument(
        "--comparators", default="",
        help="Comma-separated comparators (default: all other available cases)",
    )
    case_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    case_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the dossier against the output schema and database before printing",
    )

    # ---- research-gaps ----
    rg_parser = subparsers.add_parser(
        "research-gaps",
        help="Research gap prioritization and evidence expansion plan (Step 9)",
    )
    rg_parser.add_argument(
        "--case", default=None,
        help="Filter gaps to a jurisdiction (default: all cases)",
    )
    rg_parser.add_argument(
        "--dimension", default=None,
        help="Filter gaps to one of the 12 governance dimensions",
    )
    rg_parser.add_argument(
        "--priority", default=None,
        choices=["high", "medium", "low"],
        help="Minimum priority level to include",
    )
    rg_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    rg_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the plan against the output schema and database before printing",
    )

    # ---- findings ----
    findings_parser = subparsers.add_parser(
        "findings",
        help="Evidence Re-analysis & Research Findings Synthesis (Step 11)",
    )
    findings_parser.add_argument(
        "--case", default=None,
        help="Filter findings to a jurisdiction (default: all cases)",
    )
    findings_parser.add_argument(
        "--dimension", default=None,
        help="Filter findings to one of the 12 governance dimensions",
    )
    findings_parser.add_argument(
        "--format", choices=["json", "markdown"], default="json",
        help="Output format",
    )
    findings_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the report against the output schema and database before printing",
    )

    # ---- case-narrative ----
    narrative_parser = subparsers.add_parser(
        "case-narrative",
        help="Evidence-traceable case-study narrative draft (Step 12)",
    )
    narrative_parser.add_argument(
        "--case", required=True,
        help="Jurisdiction to build the narrative for (e.g. Ethiopia)",
    )
    narrative_parser.add_argument(
        "--comparators", default="",
        help="Comma-separated comparators (default: all other available cases)",
    )
    narrative_parser.add_argument(
        "--format", choices=["json", "markdown"], default="json",
        help="Output format",
    )
    narrative_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the narrative against the output schema and database before printing",
    )

    # ---- academic-draft ----
    academic_parser = subparsers.add_parser(
        "academic-draft",
        help="Evidence-backed academic research draft (Step 13)",
    )
    academic_parser.add_argument(
        "--case", default=None,
        help="Jurisdiction to build the draft for (default: Ethiopia)",
    )
    academic_parser.add_argument(
        "--comparators", default="",
        help="Comma-separated comparators (default: all other available cases)",
    )
    academic_parser.add_argument(
        "--format", choices=["json", "markdown"], default="json",
        help="Output format",
    )
    academic_parser.add_argument(
        "--validate", action="store_true",
        help="Validate the draft against the output schema and database before printing",
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        initialize_db()
        print("Database initialized.")
    elif args.command == "source":
        _source_command(args)
    elif args.command == "evidence":
        _evidence_command(args)
    elif args.command == "ingest":
        if args.type == "json":
            summary = import_from_json(args.file, args.source_id)
        else:
            summary = import_from_csv(args.file, args.source_id)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.command == "observation":
        evidence_ids = [int(x.strip()) for x in args.evidence_ids.split(",") if x.strip()]
        try:
            obs = create_observation({
                "jurisdiction": args.jurisdiction,
                "system_name": args.system,
                "dimension": args.dimension,
                "indicator": args.indicator,
                "observed_evidence": args.observed_evidence,
                "assessment": args.assessment,
                "confidence": args.confidence,
                "analytical_notes": args.notes,
            }, evidence_ids)
            print(f"Created observation {obs.observation_id}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "compare":
        data = get_comparative_data(args.j1, args.j2)
        if args.format == "json":
            print(comparison_to_json(data))
        else:
            print(comparison_to_csv(data))
    elif args.command == "extract":
        try:
            result = extract_text(args.file, source_id=args.source_id)
        except NotImplementedError as e:
            print(f"Error: {e}")
            sys.exit(1)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if result["status"] == "text_extraction_unavailable":
                print("text_extraction_unavailable: no extractable text (scanned/image-only PDF?)")
            else:
                print(result["text"])
    elif args.command == "research-status":
        print(report_to_json(research_status_report()))
    elif args.command == "research-matrix":
        data = research_matrix(jurisdiction=args.jurisdiction)
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(matrix_to_csv(data))
    elif args.command == "coverage-matrix":
        data = coverage_matrix()
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            import csv as _csv
            import io as _io
            buf = _io.StringIO()
            writer = _csv.writer(buf)
            writer.writerow(["jurisdiction", "governance_dimension", "source_count",
                             "evidence_count", "observation_count", "status"])
            for row in data:
                writer.writerow([row["jurisdiction"], row["governance_dimension"],
                                 row["source_count"], row["evidence_count"],
                                 row["observation_count"], row["status"]])
            print(buf.getvalue())
    elif args.command == "baseline":
        data = comparative_baseline(args.j1, args.j2)
        if args.format == "json":
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            import csv as _csv
            import io as _io
            buf = _io.StringIO()
            writer = _csv.writer(buf)
            writer.writerow(["dimension", "j1_status", "j1_evidence_count",
                             "j2_status", "j2_evidence_count", "comparison_note"])
            for dim in data["dimensions"]:
                writer.writerow([
                    dim["dimension"],
                    dim[args.j1]["evidence_status"],
                    dim[args.j1]["evidence_count"],
                    dim[args.j2]["evidence_status"],
                    dim[args.j2]["evidence_count"],
                    dim["comparison_note"],
                ])
            print(buf.getvalue())
    elif args.command == "relation":
        if args.list:
            print(json.dumps(get_evidence_relations(args.evidence_a), indent=2, ensure_ascii=False))
        else:
            if args.evidence_b is None or args.type is None:
                print("Error: --evidence-b and --type are required unless --list is used.")
                sys.exit(1)
            try:
                rel = create_evidence_relation(args.evidence_a, args.evidence_b, args.type, args.notes)
                print(f"Created relation {rel.id}: {args.evidence_a} -{args.type}-> {args.evidence_b}")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
    elif args.command == "comparative":
        cases = [c.strip() for c in args.cases.split(",") if c.strip()] or None
        report = comparative_analysis(cases)
        if args.validate:
            validate_report(report)
        if args.format == "json":
            print(analysis_to_json(report))
        else:
            print(analysis_to_csv(report))
    elif args.command == "case-study":
        comparators = [c.strip() for c in args.comparators.split(",") if c.strip()] or None
        try:
            dossier = case_study_dossier(args.case, comparators)
            if args.validate:
                validate_dossier(dossier)
            if args.format == "json":
                print(dossier_to_json(dossier))
            else:
                print(dossier_to_markdown(dossier))
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "research-gaps":
        try:
            plan = research_plan(case=args.case, dimension=args.dimension,
                                 min_priority=args.priority)
            if args.validate:
                validate_plan(plan)
            if args.format == "json":
                print(plan_to_json(plan))
            else:
                print(plan_to_markdown(plan))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "findings":
        try:
            report = build_findings_report(case=args.case, dimension=args.dimension)
            if args.validate:
                validate_findings(report)
            if args.format == "json":
                print(findings_to_json(report))
            else:
                print(findings_to_markdown(report))
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "case-narrative":
        comparators = [c.strip() for c in args.comparators.split(",") if c.strip()] or None
        try:
            narrative = case_study_narrative(args.case, comparators)
            if args.validate:
                validate_narrative(narrative)
            if args.format == "json":
                print(narrative_to_json(narrative))
            else:
                print(narrative_to_markdown(narrative))
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.command == "academic-draft":
        comparators = [c.strip() for c in args.comparators.split(",") if c.strip()] or None
        try:
            draft = build_academic_draft(args.case, comparators)
            if args.validate:
                validate_academic_draft(draft)
            if args.format == "json":
                print(academic_to_json(draft))
            else:
                print(academic_to_markdown(draft))
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()


def _source_command(args):
    if args.subcommand == "add":
        data = {
            "title": args.title,
            "source_type": args.type,
            "publisher_or_author": args.pub,
            "jurisdiction": args.jur,
            "publication_date": args.date,
            "url": args.url,
            "jurisdiction_group": args.group,
        }
        if args.status:
            data["status"] = args.status
        source = add_source(data)
        print(f"Added source: {source.source_id}")
    elif args.subcommand == "list":
        for s in list_sources(status=args.status, jurisdiction_group=args.group):
            print(_source_row(s))
    elif args.subcommand == "show":
        s = get_source(args.id)
        if not s:
            print(f"Source {args.id} not found.")
            sys.exit(1)
        print(json.dumps({
            "source_id": s.source_id,
            "title": s.title,
            "source_type": s.source_type,
            "publisher_or_author": s.publisher_or_author,
            "publication_date": str(s.publication_date) if s.publication_date else None,
            "jurisdiction": s.jurisdiction,
            "jurisdiction_group": s.jurisdiction_group,
            "institution": s.institution,
            "url": s.url,
            "status": s.status,
            "research_priority": s.research_priority,
            "research_domains": s.research_domains,
            "data_status": s.data_status,
            "description": s.description,
            "raw_integrity": verify_raw_source(s.source_id),
        }, indent=2, ensure_ascii=False))
    elif args.subcommand == "status":
        try:
            update_source_status(args.id, args.status)
            print(f"Updated source {args.id} to {args.status}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.subcommand == "import":
        try:
            summary = import_source_manifest(args.file)
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.subcommand == "acquire":
        try:
            provenance = acquire_source(args.id)
            print(json.dumps(provenance, indent=2, ensure_ascii=False))
        except (ValueError, urllib.error.URLError) as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif args.subcommand == "verify":
        print(verify_raw_source(args.id))
    else:
        print("source: add | list | show | status | import | acquire | verify")


def _evidence_command(args):
    if args.subcommand == "list":
        query = Evidence.select()
        if args.source_id:
            query = query.where(Evidence.source == args.source_id)
        for e in query:
            print(_evidence_row(e))
    elif args.subcommand == "show":
        e = Evidence.get_or_none(Evidence.evidence_id == args.id)
        if not e:
            print(f"Evidence {args.id} not found.")
            sys.exit(1)
        payload = {
            "evidence_id": e.evidence_id,
            "title": e.title,
            "claim": e.claim,
            "evidence_summary": e.evidence_summary,
            "source_excerpt": e.source_excerpt,
            "interpretation": e.interpretation,
            "data_status": e.data_status,
            "locator_type": e.locator_type,
            "locator_value": e.locator_value,
            "source": {
                "source_id": e.source.source_id,
                "title": e.source.title,
                "url": e.source.url,
                "data_status": e.source.data_status,
            },
            "linked_observations": [eo.observation.observation_id for eo in e.observation_links],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.subcommand == "init":
        initialize_db()
        print("Database initialized.")
    else:
        print("evidence: list | show | init")


if __name__ == "__main__":
    main()
