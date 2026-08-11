# Evidence Findings Synthesis (Step 11)

The findings layer re-analyzes the committed evidence corpus and turns it into a
reproducible, **evidence-backed synthesis** of what the current research
records establish — and, explicitly, what they do **not** establish. It is the
structured layer from which the final academic narrative can later be written.
It is **not** the final paper and **not** a scoring, ranking or assessment
system.

```bash
# Full report (JSON)
python -m src.cli findings

# Validated against the output schema AND the committed database
python -m src.cli findings --validate

# Primary-case focus
python -m src.cli findings --case Ethiopia

# One governance dimension, human-readable
python -m src.cli findings --dimension data_localization --format markdown
```

## What it builds on

The findings layer is a **computed view** over existing layers — it introduces
**no parallel evidence model and no new database tables**:

- Step 7 `case_dimension_view` for every (case, dimension) cell
  (status, evidence refs, observation refs, conflicts, confidence)
- Step 9 `discover_gaps()` for current research gaps
- Step 9 gap-closure record committed in `data/evidence/resolved_gaps.json`
- Step 6 matrix helpers (`_jurisdiction_evidence_ids`, statuses)

## Report structure

| section | contents |
|---|---|
| `report` / `methodology` | report type, schema version, deterministic methodology block |
| `corpus_state` | source/evidence/observation/relation counts, cases, `corpus_digest` (SHA-256 over sorted evidence + observation ids) |
| `cases` | case profiles with evidence/source counts and covered dimensions |
| `dimensions` | per-dimension summary: per-case status/counts/confidence + linked finding ids |
| `findings` | one per-cell finding for every available case & dimension |
| `comparative_findings` | Ethiopia-primary pairwise findings (comparative_finding or evidence_limitation) |
| `cross_dimension_findings` | shared-source patterns, recurring evidence limitations, no-causal-inference boundary |
| `ethiopia_synthesis` | Ethiopia as the primary case: status counts, coverage, average confidence |
| `evidence_coverage` | flattened (case, dimension) coverage rows |
| `resolved_research_gaps` | committed record of gaps closed by later evidence (Step 10) |
| `remaining_research_gaps` | the live `discover_gaps()` inventory |
| `limitations` | explicit integrity limitations of the report |

## Finding types (controlled vocabulary)

| type | when it is produced |
|---|---|
| `supported_finding` | cell has >=2 real evidence records across >=2 sources |
| `partial_finding` | cell has >=1 real record (single-source / single-record basis) |
| `conflicting_finding` | a recorded `contradicts` relation inside the cell |
| `evidence_limitation` | the corpus does not support a conclusion (empty cell, or a one-sided / empty comparative pair) |
| `comparative_finding` | both sides of an Ethiopia-primary pair hold evidence |
| `research_gap` | reserved gateway type for future gap-surfaced findings |

Each finding carries `statement_origin` (`evidence_derived` |
`analytical_interpretation` | `corpus_limitation`) so it is always clear whether
the statement summarizes evidence, classifies evidence, or describes corpus
limits.

## Layering rule (never blurred)

- `evidence_refs` — traceable records; the finding's `statement` is derived from
  counts/status only, while the records' `claim` text is preserved in the refs.
- `observation_refs` / `interpretation` — observation assessments are kept in a
  separate field and are **never silently merged into the statement**.
- `limitations` — explicit list of what the corpus cannot support.
- `research_gap_refs` — pointers to the live Step 9 gaps, not duplicated
  definitions.

Interpretation text is therefore never converted into evidence and missing
evidence is never converted into a negative finding.

## Confidence

`confidence` reuses the governance-observation `confidence` (integers 1-5) and
is the **rounded mean** over linked observations (the same deterministic
aggregation the evidence matrix uses). It is a corpus-confidence summary, never
a statistical certainty, and is `None` when no linked observation exists.
Comparative findings use `confidence: null` and keep each side's confidence in
the `comparison` block, because averaging across cases would be misleading.

## Comparative rule

- A `comparative_finding` is produced **only** when both sides of an
  Ethiopia-primary pair hold evidence.
- `support_relation` ∈ {`both_supported`, `ethiopia_more_supported`,
  `comparator_more_supported`, `broadly_similar`, `conflicting`} is an
  **analytical classification** (`statement_origin: analytical_interpretation`)
  of recorded coverage, not a score or ranking.
- Unequal or absent coverage becomes a `comparative_finding`-style
  `evidence_limitation` with pattern `insufficient_evidence` / `not_comparable`
  and an explicit coverage-imbalance limitation.

## Cross-dimension patterns (never causal)

- `shared_source_pattern` — one source contributes evidence to >=2 governance
  dimensions. The statement explicitly records an evidence-distribution
  **pattern**, not a causal link.
- `recurring_evidence_limitation` — Ethiopia's covered dimensions whose evidence
  rests entirely on normative/institutional text.
- `no_causal_inference` — the report's explicit integrity boundary: no
  causation, no numeric governance scores, indices or rankings.

## Resolved research gaps (Step 10 closure)

`data/evidence/resolved_gaps.json` is a **committed, version-controlled record**
of research gaps that a later evidence round closed:

| gap | resolving evidence |
|---|---|
| `ETHIOPIA-transparency-evidence_coverage` | 28, 29, 33 |
| `ETHIOPIA-interoperability-evidence_coverage` | 26, 31 |
| `ETHIOPIA-data_localization-source_diversity` | 27, 30 |
| `ETHIOPIA-data_localization-methodological_limitation` | 27, 30 |
| `EUROPEAN_UNION-data_localization-evidence_coverage` | 32 |

Validation requires that each recorded `gap_id` is **absent** from the live
`discover_gaps()` output and that every `resolving_evidence_ids` entry really
belongs to the recorded (jurisdiction, dimension) cell. The remaining gaps
remain visible in `remaining_research_gaps` and as `research_gap_refs` /
`evidence_limitation` findings.

## Determinism and reproducibility

The report is a **pure function of the committed database**:

- no timestamps or process-generated values are emitted
- reporting order is fixed (sorted jurisdictions, fixed 12-dimension order,
  sorted finding ids, sorted gap ids)
- `corpus_digest` changes if and only if the evidence or observation id set
  changes

Identical database state therefore produces byte-identical JSON.

## Validation

`validate_findings(report)` enforces the schema (Pydantic v2) **and** database
integrity:

- controlled vocabularies (`finding_type`, `statement_origin`, patterns)
- valid jurisdiction/dimension/status/confidence values
- every substantive finding has evidence references
- per-cell evidence refs ⊆ `_jurisdiction_evidence_ids(jurisdiction, dimension)`
- observation refs belong to the cell; research-gap refs resolve in
  `discover_gaps()`
- comparative findings have exactly two cases and a populated `comparison`
  block whose evidence belongs to the respective cells
- unique finding ids across each section
- resolved-gap closure record is consistent with the live gap inventory
- `corpus_digest` matches the current database state

## Integrity rules

1. No facts are invented; findings derive only from the committed database.
2. `missing_evidence` is never a negative assessment (absence of evidence is
   not evidence of absence).
3. No numeric governance scores, indices or rankings are produced.
4. Co-occurrence across dimensions is a pattern, never a causal claim.
5. Conflicts stay recorded and unresolved until an authoritative record exists.
6. The report is reproducible: identical state ⇒ identical output.