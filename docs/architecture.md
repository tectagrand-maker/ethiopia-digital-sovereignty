# Architecture

This project is a research-data layer for comparative digital governance. It
tracks sources, extracts evidence, builds governance observations and produces
auditable comparative output.

## Pipeline

```
SOURCE REGISTRY
      ↓
RAW SOURCE            data/raw/<source_id>/  (+ provenance.json with SHA-256)
      ↓
TEXT EXTRACTION       src/evidence/extraction.py  (txt / html / pdf)
      ↓
EVIDENCE              src/evidence/models.py, src/evidence/ingestion.py
      ↓
GOVERNANCE OBSERVATION  src/governance/analysis.py
      ↓
COMPARISON            JSON / CSV
      ↓
CASE-STUDY DOSSIER    src/governance/casestudy.py  (Step 8)
      ↓
RESEARCH GAPS         src/governance/research_gaps.py  (Step 9)
      ↓
FINDINGS SYNTHESIS    src/governance/findings.py  (Step 11)
```

## Components

### src/evidence/

- `models.py` — SQLite models (Peewee): `Source`, `Evidence`,
  `GovernanceObservation`, `EvidenceObservation` (many-to-many link table), plus
  controlled-vocabulary enums (`SourceType`, `SourceStatus`, `DataStatus`,
  `ResearchPriority`, `JurisdictionGroup`, `GOVERNANCE_DIMENSIONS`,
  `RESEARCH_DOMAINS`).
- `ingestion.py` — Pydantic v2 schema for evidence and JSON/CSV import with
  per-record error summaries.
- `collection.py` — source registry operations, deterministic deduplication,
  controlled acquisition (`acquire_source`), local raw storage
  (`save_raw_source`), SHA-256 integrity verification (`verify_raw_source`),
  and source-manifest import.
- `extraction.py` — text extraction returning structured provenance
  (extractor, version, timestamp, sha256, pages). PDF extraction uses `pypdf`;
  image-only PDFs are flagged `text_extraction_unavailable` (no OCR).

### src/governance/

- `analysis.py` — validated governance observations, database-backed comparison
  across 12 dimensions, JSON and CSV output. Missing evidence is reported as
  `missing_evidence`, never as a score.
- `status.py` — `research_status_report()` research-coverage report.
- `findings.py` — Step 11 evidence findings synthesis: deterministic,
  schema-validated report built only from the committed database (per-cell
  findings, comparative findings, cross-dimension patterns, Ethiopia primary
  synthesis, resolved/remaining research gaps). See
  `docs/findings-synthesis.md`.

### src/cli.py

Command-line interface (standard library `argparse`). See README for commands.

## Data flow rules

- Every `Evidence` belongs to a `Source` (foreign key).
- Every `GovernanceObservation` links to one or more validated `Evidence` IDs.
- Raw sources are stored read-only with a recorded SHA-256 hash.
- `source_excerpt` (what the source says), `evidence_summary` (researcher
  summary), `claim` (proposition) and `interpretation` (analysis) are separate
  fields and must not be collapsed.
- Every record carries `data_status`: `real`, `synthetic` or `methodological`.
