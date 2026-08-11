# Research Gap Prioritization & Evidence Expansion Framework (Step 9)

This framework turns the committed evidence database into a reproducible
**research plan**: which gaps should be researched next, why they matter, what
evidence is missing, and what type of source would appropriately address each
gap. It builds directly on the Step 6 matrix, Step 7 comparative analysis and
Step 8 case-study layers — it is **not** a parallel evidence or governance
system.

```bash
# Full research plan (JSON)
python -m src.cli research-gaps

# Filtered, validated, human-readable
python -m src.cli research-gaps --case Ethiopia --dimension transparency \
  --priority medium --validate --format markdown

# Minimum priority filter
python -m src.cli research-gaps --priority high
```

## How gaps are discovered

Gaps are **derived** from the database, never manually invented. For every
available case and every governance dimension, the framework reuses the Step 7
`case_dimension_view` cell (status, evidence, conflicts, confidence, gaps) and
the underlying `Evidence` records, then applies deterministic rules:

| category | rule that fires |
|---|---|
| `evidence_coverage` | the cell has **no** real evidence records (`missing_evidence`) |
| `source_diversity` | the cell has evidence but from **one source only** (partial) |
| `source_quality` | cell evidence has provenance deficiencies: missing locator, missing `evidence_basis`, `evidence_strength`/`reliability_level` <= 2, or an unaccessed source |
| `temporal_coverage` | cell evidence lacks an independently verified `publication_date` |
| `confidence_limitation` | linked observations carry average `confidence` <= 2 |
| `methodological_limitation` | evidence exists but no observation synthesizes it, **or** the cell's evidence is exclusively normative/institutional (no implementation/empirical/observational records) |
| `conflicting_evidence` | linked evidence carries a recorded `contradicts` relation (the pairs are listed, never silently resolved) |
| `comparative_coverage` | a coverage imbalance or a shared empty cell across cases (Step 7) |

Only categories the data model can actually support are implemented; there are
no decorative categories.

## Gap scopes

Each gap is tagged with one of four scopes (spec requirement 9):

- `ethiopia_specific` — a per-cell gap whose affected case is Ethiopia
- `comparator_specific` — a per-cell gap whose affected case is a comparator
- `cross_case` — the same dimension is empty in every available case
- `comparative_coverage` — a coverage imbalance between Ethiopia and a comparator

`comparator_context` on comparative gaps records the pairwise statuses so the
reader can see exactly which side lacks evidence.

## How prioritization works

Prioritization is **rule-based and explainable**. Each gap receives:

- `priority_score` — an integer from the documented formula
- `priority_level` — `high` (score >= 7), `medium` (score >= 5), `low` (< 5)
- `priority_factors` — one entry per contributing rule with points and rationale
- `priority_rationale` — a plain-text explanation of the score

### Formula

```
score = dimension_importance + severity + breadth        (max 9)
```

- **dimension_importance** (1-3) — the project's documented research-focus
  weight per dimension (see `DIMENSION_IMPORTANCE` in
  `src/governance/research_gaps.py`). It reflects what this research program
  prioritizes, **not** an assessment of a dimension's real-world importance.
- **severity** (1-3) — `evidence_coverage` and `conflicting_evidence` weigh 3;
  `source_diversity` and `comparative_coverage` weigh 2; provenance, temporal,
  confidence and methodological limitations weigh 1.
- **breadth** (0-3), one point each for:
  - the gap affects the primary case (Ethiopia);
  - another case already holds evidence on the dimension (comparative
    importance — closing the gap would enable/refresh a pairwise comparison);
  - the cell is currently `partial` or `conflicting` (resolving the gap could
    materially change the interpretation).

> **Important**: `priority_score` is a **research-planning heuristic**. It is
> never a governance score, a country ranking, or a judgment about a
> jurisdiction. The disclaimer is reproduced in every plan's
> `methodology.disclaimer` and in the CLI output's limitations section.

### Interpreting priorities

A `high` gap is one the research program should attempt to close next, given
the dimension's research focus, the severity of the evidence insufficiency and
the breadth of downstream analysis it affects. A `low` gap still matters; it is
just less central to the current research focus or is on a dimension with a
thinner analytical footprint.

## Research actions and evidence-source strategy

Every gap produces one structured `ResearchAction`:

- `gap_id`, `jurisdiction`, `dimension`, `category`, `scope`
- `reason` — why the gap exists (the rule that fired)
- `evidence_available` — evidence ids currently in the corpus for the cell
- `evidence_missing` — what is not recorded (never a negative verdict)
- `recommended_source_types` — from the documented category → SourceType
  mapping (see `RECOMMENDED_SOURCE_TYPES`). For example, `evidence_coverage`
  gaps recommend `law`/`regulation`/`policy`/`government_document`/
  `official_webpage`; `methodological_limitation` gaps recommend
  `technical_report`/`institutional_report`/`dataset`/`civil_society_report`
  (implementation/empirical evidence). No type is automatically claimed
  authoritative for every dimension.
- `recommended_catalog_sources` — ids of catalog sources that are already
  `discovered` (not yet acquired) and whose research domains map onto the
  dimension, e.g. the Fayda portal (`#7`) for `interoperability`.
- `research_question` — a question prompt (always ends in `?`), never a claim
- `expected_analytical_value` — what resolving the gap would enable
- `dependencies` — documented prerequisites
- `provenance_requirements` — the standard source→acquire→verify→extract→ingest
  checklist

## How future evidence should be added

New evidence must flow through the existing ingestion/provenance system.
`evidence_expansion_requirements()` returns the checklist; `validate_evidence_record()`
pre-validates a prospective record against `EvidenceSchema` **without inserting
anything**:

```python
from src.governance.research_gaps import (
    evidence_expansion_requirements, validate_evidence_record,
)
print(evidence_expansion_requirements()["provenance_steps"])
validate_evidence_record({...})   # {'valid': bool, ...}
```

The required pipeline (never bypassed):

1. Register the source (`source add`, or extend `data/sources/catalog.json`).
2. Acquire the raw source (`source acquire --id <id>`, records SHA-256).
3. Verify integrity (`source verify --id <id>`).
4. Extract text (`extract --file <raw> --source-id <id>`).
5. Ingest evidence (`ingest --type json --file <corpus> --source-id <id>`).
6. Link governance observations to the new evidence ids where a dimension
   assessment is expected.

Unverified material must never be inserted directly into the evidence database.

## The research plan output

`research_plan()` returns a deterministic, machine-readable plan:

- `gaps` — the full gap inventory, sorted by (priority, then id)
- `prioritized_actions` — one action per gap, same order
- `affected_dimensions`, `affected_cases`
- `evidence_coverage` — compact per-case/per-dimension status grid for the
  affected scope
- `research_questions`, `recommended_source_types`
- `methodology` — the documented formula, weights, thresholds and disclaimer
- `limitations` — honest caveats about automated gap prioritization

## Integration with Steps 7-8

- **Step 7 (comparative):** `comparative_coverage` and `cross_case` gaps are
  generated from the same `case_dimension_view` cells the comparative report
  uses, so the two never disagree about coverage.
- **Step 8 (case-study):** every dossier now carries `gap_references` — compact
  `{gap_id, category, scope, dimension, evidence_status, priority_level}`
  entries that **reference** the research-gap plan without duplicating the
  underlying definitions. Writers can jump from a dossier to
  `python -m src.cli research-gaps` for the full action.

## Avoiding "missing evidence = evidence of absence"

Throughout the framework:

- `missing_evidence` and `evidence_missing` describe **corpus coverage**.
- `evidence_coverage` gaps say "no evidence is recorded", never "this is bad".
- Research questions are prompts for future work, not findings.
- Contradictions are listed, never resolved.
- The methodology disclaimer and the limitations section are emitted in every
  plan so the rule is visible in the output itself.

## Validation

`validate_plan()` (also `--validate` on the CLI) enforces:

- valid gap identifiers and no duplicates;
- valid jurisdictions (available cases or the `Cross-case` sentinel);
- valid governance dimensions, categories, scopes and priority levels;
- every evidence reference exists and matches the gap's jurisdiction
  (no orphans, provenance consistency);
- one research action per gap with matching `gap_id`/priority;
- every research question is phrased as a question;
- deterministic ordering (priority desc, id asc);
- stable serialization (identical JSON across runs).

## Limitations of automated gap prioritization

- Gaps come only from the committed corpus; unacquired sources cannot generate
  evidence and therefore cannot generate per-cell evidence.
- Priority reflects research focus + corpus state, not real-world importance.
- `missing_evidence` is never a negative finding.
- Recommended source types are guidance; no type is universally authoritative.
- Comparative/cross-case gaps depend on which cases exist in `available_cases()`.

## Verification

```bash
python -m src.cli research-gaps --validate        # schema + integrity check
python -m src.cli research-status                 # Step 6 coverage report
python -m src.cli research-gaps --format markdown # planning view
```
