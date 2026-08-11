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
- An evidence-backed case-study dossier framework (JSON / Markdown)
- A research-gap prioritization and evidence-expansion framework
- A deterministic evidence-findings synthesis layer (Step 11)
- A deterministic evidence-traceable case-study narrative layer (Step 12)
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
      ↓
CASE-STUDY DOSSIER
      ↓
RESEARCH-GAP PRIORITIZATION
      ↓
EVIDENCE FINDINGS SYNTHESIS
      ↓
CASE-STUDY NARRATIVE
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
python -m src.cli ingest --type json --file data/evidence/corpus/source_12_kenya_dpa.json --source-id 12
python -m src.cli ingest --type csv --file data/examples/demo_evidence.csv --source-id 1
```

The committed corpus lives in `data/evidence/corpus/` and is imported by
`corpus_manifest.json`. The whole database (sources, evidence, observations)
can be rebuilt reproducibly from committed files:

```bash
python scripts/rebuild_db.py --drop
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

## Comparative governance analysis (Step 7)

```bash
python -m src.cli comparative                              # all available cases
python -m src.cli comparative --cases Ethiopia,Kenya --format json
python -m src.cli comparative --cases Ethiopia,Kenya --format csv
python -m src.cli comparative --validate                   # schema-check before printing
```

Multi-case analysis across the 12 dimensions where each cell explicitly
distinguishes supported evidence, missing evidence, conflicting evidence,
analytical interpretation and research gaps. Every cell's evidence list is
traceable to source, locator and citation. Never a ranking or a score.

## Case-study framework (Step 8)

```bash
python -m src.cli case-study --case Ethiopia --validate --format json   # validated dossier
python -m src.cli case-study --case Kenya --format markdown             # narrative-ready rendering
python -m src.cli case-study --case Ethiopia --comparators Kenya,European\ Union
```

Builds a deterministic, evidence-backed dossier for one jurisdiction: case
identity, one profile for each of the 12 governance dimensions, a synthesis of
supported/partial/conflicting/missing evidence, and a comparative-context block
that references the Step 7 baseline. Every claim stays traceable to an evidence
id; the dossier is validated against a pydantic schema and the database
(`--validate`). It is the structured layer from which narrative case-study
writing is generated, never a score or ranking. See
`docs/case-study-framework.md`.

## Research-gap prioritization framework (Step 9)

```bash
python -m src.cli research-gaps                                 # full plan (JSON)
python -m src.cli research-gaps --case Ethiopia --priority high  # filter by case/priority
python -m src.cli research-gaps --dimension transparency --format markdown
python -m src.cli research-gaps --validate                       # schema + integrity check
```

Derives research gaps from the committed evidence database, classifies them
(`evidence_coverage`, `source_diversity`, `source_quality`, `temporal_coverage`,
`confidence_limitation`, `methodological_limitation`, `conflicting_evidence`,
`comparative_coverage`), prioritizes them with a documented, explainable rule
(never a governance score or country ranking), and generates structured
research actions with recommended source types and research questions.
Evidence expansion always flows through the ingestion/provenance pipeline
(`evidence_expansion_requirements()` / `validate_evidence_record()`). See
`docs/research-gap-framework.md`.

## Evidence findings synthesis (Step 11)

```bash
python -m src.cli findings                          # full synthesis report (JSON)
python -m src.cli findings --validate               # schema + database integrity check
python -m src.cli findings --case Ethiopia          # primary-case focused report
python -m src.cli findings --dimension data_localization --format markdown
```

Re-analyzes the committed evidence corpus into a deterministic, evidence-backed
findings layer: per-cell findings (supported / partial / conflicting /
evidence_limitation), comparative findings only where both sides hold evidence,
cross-dimension (non-causal) patterns, and the Ethiopia primary-case synthesis.
`missing_evidence` is a corpus statement, never a negative finding; no scores,
indices or rankings are produced. The report is a pure function of the database
(identical state -> identical JSON). See `docs/findings-synthesis.md`.

## Case-study narrative (Step 12)

```bash
python -m src.cli case-narrative --case Ethiopia --validate --format json   # validated draft (JSON)
python -m src.cli case-narrative --case Ethiopia --format markdown          # prose draft w/ inline [ev] citations
python -m src.cli case-narrative --case Ethiopia --comparators Kenya        # explicit comparator set
```

Builds a deterministic, evidence-traceable **narrative draft** on top of the
Step 8 dossier, the Step 11 findings and the Step 9 gaps. Every claim carries
`statement_origin` (`evidence_derived | analytical_interpretation |
corpus_limitation`) and its evidence ids; claims without evidence are explicit
corpus limitations, never verdicts. The output includes a traceability manifest
mapping every evidence id to the sections that cite it, and is validated against
the pydantic schema and the committed database (`--validate`). It is draft
material for the final writing phase, never a score or ranking. See
`docs/case-narrative.md`.

## Research status

```bash
python -m src.cli research-status
```

Produces a research-coverage report (source counts, evidence counts, dimensions
with missing evidence, locator completeness, single/multi-source observations,
unresolved contradictions). It is a data-quality report, not a governance score.

## Research matrix, coverage and baseline (Step 6)

```bash
python -m src.cli research-matrix --jurisdiction Ethiopia   # 12-dimension Ethiopia matrix
python -m src.cli coverage-matrix --format csv              # jurisdiction x dimension grid
python -m src.cli baseline --j1 Ethiopia --j2 Kenya         # methodological comparative baseline
python -m src.cli relation --evidence-a 1 --evidence-b 19 --type contextualizes --notes "..."
```

Evidence records carry an `evidence_basis` classification
(`normative | institutional | technical | empirical | implementation |
observational`) describing what a record can establish. Relations between
evidence records (`supports | qualifies | contradicts | contextualizes`) are
recorded without silently resolving conflicts. See
`docs/evidence-matrix.md` and `docs/research-gaps.md`.

## Running tests

```bash
python -m pytest
```

## Demo data warning

Files under `data/examples/` and the synthetic records created in tests are
**demonstration fixtures**. Synthetic records are explicitly labelled
`data_status: synthetic`. Do not present them as real research findings.

## Documentation

- `docs/architecture.md` — the evidence → governance → comparison pipeline
- `docs/evidence-methodology.md` — source vs evidence vs claim vs interpretation
- `docs/source-collection.md` — source registry, acquisition, provenance, integrity
- `docs/comparative-analysis.md` — dimensions, observations, missing evidence,
  and the Step 7 comparative governance analysis
- `docs/case-study-framework.md` — the Step 8 evidence-backed case-study dossier
  framework (data model, validation, narrative workflow)
- `docs/research-gap-framework.md` — the Step 9 research-gap prioritization and
  evidence-expansion framework (discovery, classification, prioritization,
  research actions, how to add evidence)
- `docs/evidence-matrix.md` — Step 6 matrix, status derivation, evidence basis
- `docs/research-gaps.md` — current corpus gaps and priorities
- `docs/findings-synthesis.md` — the Step 11 evidence findings synthesis layer
  (schemas, confidence rule, comparative rule, cross-dimension patterns,
  resolved-gap closure record, report validation)
- `docs/case-narrative.md` — the Step 12 evidence-traceable case-study narrative
  layer (claim model, traceability manifest, validation, writing workflow)

## Current limitations

- Only a subset of catalog sources have been acquired and extracted so far.
- PDF text extraction is `pypdf`-based and does not handle image-only PDFs (no OCR).
- Ethiopia governance observations cover 11 of 12 dimensions; Step 10 raised
  `transparency` and `interoperability` to `supported`, while
  `private_sector_dependence` remains `missing_evidence` for Ethiopia.
- The comparative baseline and the Step 7 pairwise notes classify patterns from
  confidence and must be read together with the interpretation text (see
  `docs/evidence-matrix.md` and `docs/comparative-analysis.md`).
- Kenya and the EU are represented by narrow evidence bases, so most of their
  dimension cells are `missing_evidence`; the Step 11 report records this as
  explicit `evidence_limitation` / comparative-coverage findings, never as a
  negative assessment.
- The Step 12 narrative is draft material: prose sentences are deterministic
  renderings of evidence claims, interpretations and limitation statements. The
  final academic prose still needs human writing; the traceability manifest keeps
  every sentence anchored while that happens.
- No frontend/UI yet.

## What comes next

- Executing the prioritized research actions from `research-gaps` and closing
  the `high`-priority gaps through the standard ingestion pipeline.
- Writing the final case-study narrative on top of the Step 12 narrative draft
  (`docs/case-narrative.md`), the dossier framework
  (`docs/case-study-framework.md`) and the Step 11 findings layer
  (`docs/findings-synthesis.md`), keeping every statement traceable to an
  evidence id.
