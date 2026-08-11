# Case-Study Framework (Step 8)

The case-study framework turns the evidence, governance-dimension and
comparative layers (Steps 6-7) into a reproducible, research-ready case-study
**dossier** for a single jurisdiction. It is a structured, machine-readable
intermediate layer — it is **not** the final academic case-study narrative.

```bash
# JSON dossier for Ethiopia (validated against the schema before printing)
python -m src.cli case-study --case Ethiopia --validate --format json

# Deterministic markdown rendering for later narrative writing
python -m src.cli case-study --case Kenya --format markdown

# Explicit comparator set for the comparative-context block
python -m src.cli case-study --case Ethiopia --comparators Kenya,European\ Union
```

The dossier is generated entirely from the committed evidence database. No
facts, claims, sources or citations are invented.

## What the dossier contains

A `case_study_dossier` (schema version 1) has five parts:

| part | field | meaning |
|---|---|---|
| case identity | `case` | jurisdiction, title/description (from `data/cases/cases.json`), source groups, source/evidence counts, available dimensions, coverage summary |
| dimension profiles | `dimension_profiles` | one profile for **each of the 12 governance dimensions** (fixed order) |
| synthesis | `synthesis` | deterministic findings, conflicts, missing areas, patterns, limitations, priority gaps |
| comparative context | `comparative_context` | a *reference* to the Step 7 comparative baseline, not a duplication |
| envelope | `dossier_type` / `schema_version` | stable machine-readable identifiers |

## Analytical separation

Every dimension profile keeps five kinds of content strictly separate:

- `evidence` — traceable records from the corpus (`evidence_id`, `source_id`,
  `source_title`, `source_type`, `locator_type`/`locator_value`, `claim`,
  `evidence_basis`, `data_status`, `citation`, `source_url`)
- `observations` — governance observations for the dimension, each with its own
  `evidence_ids` links
- `interpretation` — the assessment text from those observations
- `analytical_notes` — free-text notes attached to the observations
- `research_gaps` — explicit statements of missing/insufficient corpus coverage

Evidence is never copied into a new structure: it is **referenced** by
`evidence_id`, and provenance is re-resolved from the database.

## Status derivation

A dimension profile's `evidence_status` follows the Step 6/7 rules:

- `supported` — >= 2 real evidence records across >= 2 sources
- `partial` — >= 1 real evidence record
- `missing_evidence` — no real evidence record for that dimension
- `conflicting` — the cell's linked evidence carries a `contradicts` relation;
  the pairs are listed in `conflicts` and surfaced in `synthesis`

`missing_evidence` is a statement about corpus coverage, **never** a negative
finding. Absence of evidence is not evidence of absence.

## Evidence → observation → interpretation → gaps

The dossier makes the analytical chain explicit:

```
source → passage (locator) → evidence record → governance observation
       → interpretation (assessment) → synthesis finding / research gap
```

- A synthesis finding (`major_supported_findings`, `partial_findings`) is only
  emitted when it can reference at least one evidence id.
- `missing_evidence_areas` lists dimensions with no evidence; the corresponding
  priority gap is stated as "No evidence for dimension X", not as a negative
  verdict.
- `priority_research_gaps` also flags dimensions that have evidence but no
  synthesizing observation, and notes that the corpus is predominantly
  normative (statutes) without independent enforcement/implementation evidence.

## Comparative context

The `comparative_context` block **references** the Step 7 comparative baseline
(`python -m src.cli comparative --cases ...`) rather than embedding a second
copy of it. For each dimension it surfaces the pairwise notes involving the
case, so a writer can navigate to the full baseline without the dossier
duplicating the comparative analysis.

## Determinism

Generation is deterministic: dimension order is fixed, cases and comparators
are sorted, and evidence/observation/conflict ordering is stable. The same
database state always produces the same dossier (JSON round-trips byte-for-byte).

## Validation

`validate_dossier()` (also `--validate` on the CLI) enforces:

- exactly the 12 governance dimensions, in the fixed order
- valid `evidence_status` values only
- every evidence reference exists in the database (no orphans)
- every profile evidence trace matches the database `source_id` and the
  dossier's jurisdiction
- every synthesis finding carries at least one evidence reference
  (no unsupported claims)
- deterministic ordering throughout

## What the framework does NOT claim

- It is not the final case-study narrative; it is the evidence layer from which
  a narrative can be written.
- It assigns no scores and no rankings (coverage is reported as counts).
- `missing_evidence` and gaps are about the corpus, not about a jurisdiction.
- Contradictions are listed, not silently resolved.
- A normative/legal record is never presented as evidence of enforcement.
- The comparative context is a pointer to the Step 7 baseline, and pairwise
  notes classify patterns from evidence confidence — read them with the
  interpretation text.

## Data model

```json
{
  "dossier_type": "case_study_dossier",
  "schema_version": 1,
  "case": {
    "jurisdiction": "Ethiopia",
    "title": "Ethiopia",
    "description": "...",
    "source_groups": ["ethiopia"],
    "source_count": 8,
    "evidence_count": 19,
    "available_dimensions": ["data_governance", "..."],
    "coverage_summary": {"supported": 7, "partial": 2, "missing_evidence": 3, "conflicting": 0}
  },
  "dimension_profiles": [
    {
      "dimension": "data_governance",
      "evidence_status": "supported",
      "evidence_count": 3,
      "source_count": 2,
      "observation_count": 1,
      "confidence": 4,
      "evidence": [ { "evidence_id": 1, "source_id": 2, "claim": "...", ... } ],
      "observations": [ { "observation_id": 1, "indicator": "...", "evidence_ids": [1] } ],
      "interpretation": ["..."],
      "analytical_notes": ["..."],
      "conflicts": [],
      "research_gaps": ["..."]
    }
  ],
  "synthesis": {
    "major_supported_findings": [ { "claim": "...", "evidence_ids": [1], "source_ids": [2] } ],
    "partial_findings": [],
    "conflicting_evidence": [],
    "missing_evidence_areas": ["transparency"],
    "cross_dimension_patterns": ["..."],
    "limitations": ["..."],
    "priority_research_gaps": ["..."]
  },
  "comparative_context": {
    "note": "...",
    "available_comparators": ["European Union", "Kenya"],
    "dimension_notes": { "consent_individual_agency": ["Ethiopia vs Kenya: similar_pattern"] }
  }
}
```

Case titles and descriptions live in the committed manifest
`data/cases/cases.json`; a jurisdiction absent from the manifest falls back to
its jurisdiction name as the title.

## Using the dossier for case-study writing

1. Generate the dossier (`--validate --format json`) for the target case.
2. Use `case.available_dimensions` and `coverage_summary` for the scope
   paragraph and to state honestly what is and is not covered.
3. For each dimension, draft narrative from `evidence` claims, the
   `interpretation` text and the `research_gaps` (never from a gap as a
   verdict).
4. Use `synthesis` to structure findings, and `comparative_context.dimension_notes`
   as pointers to the Step 7 baseline for cross-case discussion.
5. Keep every statement in the narrative traceable to an evidence id; treat
   anything without one as explicitly marked speculation.
