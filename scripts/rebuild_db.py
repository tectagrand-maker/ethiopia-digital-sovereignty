"""Rebuild the research database from committed data files (reproducibility).

Usage:
    python scripts/rebuild_db.py [--drop]

This regenerates data/evidence.db from the committed manifests under
data/sources/ and data/evidence/. Raw source documents are NOT re-downloaded;
acquired raw files must already be present under data/raw/<id>/ (see
docs/source-collection.md). If a raw file is absent the source stays
discovered rather than being marked accessed.

Note: this script creates the schema and imports committed data. It does not
create governance observations or evidence relations by itself -- those are
loaded from the committed JSON manifests when present.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evidence.models import initialize_db, Source, Evidence, GovernanceObservation, DataStatus
from src.evidence.collection import import_source_manifest, verify_raw_source, update_source_status
from src.evidence.ingestion import import_from_json
from src.governance.analysis import create_observation

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


def _drop_db():
    db_path = os.path.join(DATA, 'evidence.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Dropped {db_path}")


def _import_sources():
    manifest = os.path.join(DATA, 'sources', 'catalog.json')
    if not os.path.exists(manifest):
        return
    summary = import_source_manifest(manifest)
    print(f"Sources: read={summary['read']} accepted={summary['accepted']} "
          f"duplicates={summary['duplicates']}")


def _mark_accessed():
    """Mark sources accessed where a matching verified raw file already exists."""
    for source in Source.select():
        result = verify_raw_source(source.source_id)
        if result == 'verified' and source.status in ('discovered', 'queued'):
            update_source_status(source.source_id, 'accessed')


def _import_evidence_manifest():
    manifest = os.path.join(DATA, 'evidence', 'corpus_manifest.json')
    if not os.path.exists(manifest):
        return
    with open(manifest, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    for entry in entries:
        path = os.path.join(DATA, 'evidence', entry['file'])
        source_id = entry['source_id']
        if not os.path.exists(path):
            print(f"  missing evidence file: {path}")
            continue
        summary = import_from_json(path, source_id)
        print(f"  {entry['file']}: accepted={summary['accepted']} "
              f"duplicates={summary['duplicates']} rejected={summary['rejected']}")


def _import_observations_manifest():
    manifest = os.path.join(DATA, 'evidence', 'observations_manifest.json')
    if not os.path.exists(manifest):
        return
    with open(manifest, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    for entry in entries:
        try:
            obs = create_observation(entry['observation'], entry['evidence_ids'])
            print(f"  observation {obs.observation_id}: {entry['observation']['dimension']} "
                  f"({entry['observation']['jurisdiction']})")
        except ValueError as e:
            print(f"  SKIP observation ({entry['observation'].get('dimension')}): {e}")


def main():
    parser = argparse.ArgumentParser(description="Rebuild the research DB from committed data.")
    parser.add_argument('--drop', action='store_true', help="Drop the existing DB first")
    args = parser.parse_args()

    if args.drop:
        _drop_db()

    initialize_db()
    _import_sources()
    _import_evidence_manifest()
    _import_observations_manifest()
    _mark_accessed()
    print("Rebuild complete.")


if __name__ == '__main__':
    main()
