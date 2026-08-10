# Ethiopia Digital Sovereignty Research

A reusable, auditable research infrastructure for studying digital sovereignty,
data governance, digital identity, consent and institutional power — focused on
Ethiopia and comparable digital governance systems.

## Status

This is a **research infrastructure** repository. It currently contains:

- An SQLite evidence database with Pydantic v2 validation
- A Source Registry with deterministic deduplication and status tracking
- Controlled source acquisition with SHA-256 provenance
- TXT / HTML / PDF text extraction
- A researcher-driven evidence model (excerpt, claim, summary, interpretation)
- Governance observations linked to evidence (12 dimensions)
- Executable comparative analysis (JSON / CSV)
- A research-coverage status report
- A small **real** source catalog + a small **real** evidence corpus
- Synthetic demonstration fixtures, clearly labelled

> **Important**: This repository does **not** contain conclusions or scores about
> Ethiopia. It contains infrastructure, a source catalog, and a small evidence
> corpus. Absence of evidence is reported as `missing_evidence`, never as a score.

## Research Workflow

```
SOURCE DISCOVERY
      ↓
SOURCE REGISTRATION
      ↓
SOURCE VERIFICATION
      ↓
SOURCE ACQUISITION  →  raw source + SHA-256
      ↓
TEXT EXTRACTION     →  txt / html / pdf
      ↓
EVIDENCE EXTRACTION (researcher-entered)
      ↓
GOVERNANCE OBSERVATION
      ↓
COMPARATIVE ANALYSIS
```

## Installation

Requires Python >= 3.9.

```bash
pip install -e ".[dev]"
```

## Initialize the database

```bash
python -m src.cli init
```

## Source registry

Import the curated source catalog:

```bash
python -m src.cli source import --file data/sources/catalog.json
```

List sources (optionally filtered by status or jurisdiction group):

```bash
python -m src.cli source list
python -m src.cli source list --status discovered
python -m src.cli source list --group ethiopia
```

Show a source with integrity status:

```bash
python -m src.cli source show --id 1
```

Update source status (`discovered → queued → accessed → extracted → verified → rejected/archived`):

```bash
python -m src.cli source status --id 1 --status queued
```

Acquire (download) a selected public source into `data/raw/<source_id>/`:

```bash
python -m src.cli source acquire --id 12
```

Verify the stored raw source against its recorded SHA-256:

```bash
python -m src.cli source verify --id 12
```

Add a source manually:

```bash
python -m src.cli source add --title "Law X" --type law --pub "Agency" \
  --date 2024-01-01 --jur Ethiopia --url https://example.com/law
```

## Text extraction

```bash
python -m src.cli extract --file data/raw/12/TheDataProtectionAct__No24of2019.pdf --source-id 12 --json
```

Supported: `.txt`, `.html`, `.pdf`. Image-only PDFs are reported as
`text_extraction_unavailable` (OCR is not implemented).

## Evidence

List evidence (optionally per source):

```bash
python -m src.cli evidence list
python -m src.cli evidence list --source-id 12
```

Show evidence with full provenance (source, locator, excerpt, interpretation, linked observations):

```bash
python -m src.cli evidence show --id 1
```

Ingest evidence from JSON or CSV (linked to a source):

```bash
python -m src.cli ingest --type json --file data/evidence/real_corpus_001.json --source-id 12
python -m src.cli ingest --type csv --file data/examples/demo_evidence.csv --source-id 1
```

Evidence records distinguish `source_excerpt` (what the source says),
`evidence_summary` (structured summary), `claim` (the proposition) and
`interpretation` (analytical reading). They also carry a `data_status`:
`real`, `synthetic`, or `methodological`.

## Governance observations

```bash
python -m src.cli observation \
  --jurisdiction Kenya --system "Kenya DPA" \
  --dimension consent_individual_agency --indicator statutory_consent_definition \
  --observed-evidence "..." --assessment "..." --confidence 5 --evidence-ids 1
```

Observations must reference valid evidence IDs and use one of the 12 dimensions.

## Comparison

```bash
python -m src.cli compare --j1 Ethiopia --j2 ExampleSystem --format json
python -m src.cli compare --j1 Ethiopia --j2 Kenya --format csv
```

Dimensions without observations are reported as `missing_evidence` — never as a
negative score.

## Research status

```bash
python -m src.cli research-status
```

Produces a research-coverage report (source counts, evidence counts, dimensions
with missing evidence). It is a data-quality report, not a governance score.

## Running tests

```bash
python -m pytest
```

## Demo data warning

Files under `data/examples/`, `data/evidence/real_corpus_001.json` and the
synthetic records created in tests are **demonstration fixtures**. Synthetic
records are explicitly labelled `data_status: synthetic`. Do not present them as
real research findings.

## Documentation

- `docs/architecture.md` — the evidence → governance → comparison pipeline
- `docs/evidence-methodology.md` — source vs evidence vs claim vs interpretation
- `docs/source-collection.md` — source registry, acquisition, provenance, integrity
- `docs/comparative-analysis.md` — dimensions, observations, missing evidence

## Current limitations

- Only a small number of sources have been acquired and extracted so far.
- PDF text extraction is `pypdf`-based and does not handle image-only PDFs (no OCR).
- Governance observations exist only for a few evidence records; most dimensions
  remain `missing_evidence`.
- No frontend/UI yet.

## What comes next

- Systematic evidence extraction from the catalogued authoritative sources.
- Building a comparative case-study construction layer on the stable pipeline.
