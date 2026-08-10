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
)
from src.governance.status import research_status_report, report_to_json


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
