# Evidence-Traceable Case-Study Narrative (Step 12)

The narrative layer turns the Step 8 case-study **dossier**, the Step 11
**findings synthesis** and the Step 9 **research-gap inventory** into a
reproducible, **draft case-study narrative** whose every claim is anchored to an
evidence id. It is the structured bridge from analysis to prose writing — it is
**not** the final academic paper and it produces **no scores, indices or
rankings**.

```bash
# JSON narrative draft for Ethiopia (validated against schema + database)
python -m src.cli case-narrative --case Ethiopia --validate --format json

# Deterministic markdown rendering with inline evidence citations
python -m src.cli case-narrative --case Ethiopia --format markdown

# Explicit comparator set for the comparative narrative blocks
python -m src.cli case-narrative --case Ethiopia --comparators Kenya,European\ Union
```

## What it builds on

The narrative is a **computed view** over the existing layers — it introduces
**no parallel evidence model and no new database tables**:

- Step 8 `case_study_dossier(jurisdiction, comparators)` for the case identity,
  12 dimension profiles and the synthesis block
- Step 11 `build_findings_report(case=jurisdiction)` for per-cell findings,
  comparative findings, cross-cutting patterns
- Step 9 `discover_gaps()` for research guidance
- `case_dimension_view` / `_cell_observations` for the cell status and
  observation assessments

Because every one of these layers is itself derived only from the committed
database, the narrative inherits their determinism: the same database state
always produces byte-identical JSON and Markdown.

## Narrative structure

| section | contents |
|---|---|
| `note` / `narrative_type` / `schema_version` | stable identifiers and the traceability statement |
| `case` / `coverage_summary` | case identity plus supported/partial/missing/conflicting counts (12 dimensions) |
| `dimension_sections` | 12 sections (fixed governance-dimension order), each a list of `NarrativeClaim` |
| `comparative_sections` | Ethiopia-primary pairwise blocks (only for evidenced pairs) |
| `cross_cutting_patterns` | shared-source patterns, recurring limitations, the no-causal boundary |
| `synthesis` | major supported findings, partial findings, recorded conflicts, missing areas |
| `research_guidance` | prioritized Step 9 actions phrased as research questions |
| `traceability` | the manifest: every (evidence_id, section_id) anchor used in the prose |
| `limitations` | explicit integrity limitations of the draft |

## Claim model (the traceability invariant)

Every sentence in a narrative is a `NarrativeClaim`:

- `claim_id` — deterministic, unique within its section
- `statement` — the prose sentence
- `statement_origin` — `evidence_derived` |
  `analytical_interpretation` | `corpus_limitation`
- `evidence_ids` — the evidence record(s) backing the statement

Layering is never blurred:

- **Opening and limitation claims** are taken verbatim from the Step 11
  per-cell finding (its `statement` and `limitations`) and keep the finding's
  `statement_origin`.
- **Evidence claims** render the recorded `claim` text from the dimension
  profile's evidence traces.
- **Interpretation claims** render governance-observation `assessment` text and
  carry the observation's linked evidence ids.
- A claim with **no** evidence must be `corpus_limitation` — it is a statement
  about the corpus, never a negative assessment of the jurisdiction.

`missing_evidence` cells still produce a dimension section: it states there is
no real evidence, marks the statement as a corpus limitation, and never makes a
verdict.

## Comparative narrative

Comparative sections are produced only where the Step 11 report produced them:
a `comparative_finding` when both sides of an Ethiopia-primary pair hold
evidence, and an `evidence_limitation` block (with an explicit coverage-imbalance
limitation) when coverage is unequal or absent. Each block records the pair, the
`support_relation` classification and traceable claims.

## Cross-cutting patterns

Cross-cutting pattern statements reuse the Step 11 findings and remain
deterministic and non-causal: a shared-source pattern records an
evidence-distribution **pattern**, never a causal link, and the narrative always
includes the explicit `no_causal_inference` boundary.

## Traceability manifest

`traceability` is a flat list of `(evidence_id, section_id, dimension,
source_id, claim)` rows. It is built from the sections themselves, so:

- every evidence anchored anywhere in the prose appears in the manifest
- every manifest row corresponds to a real anchor (the manifest cannot invent
  references the narrative does not make)
- rows are deduplicated on `(evidence_id, section_id)` and sorted, keeping the
  output deterministic

## Research guidance

`research_guidance` surfaces the prioritized Step 9 gaps that touch the case,
each phrased as a research question (from the Step 9 templates) so the final
writing process can state honestly what still needs evidence — without treating
a gap as a finding.

## Determinism

- dimension sections follow the fixed 12-dimension order
- claims are ordered: opening, evidence traces (by evidence id), interpretations
  (by observation id), limitations
- comparators, pairs, evidence ids and gap references are sorted
- no timestamps or randomized content are emitted

Identical database state ⇒ byte-identical JSON and Markdown.

## Validation

`validate_narrative()` (also `--validate`) enforces the schema (Pydantic v2)
**and** database integrity:

- exactly the 12 governance dimensions, in the fixed order
- controlled `statement_origin` vocabulary and valid status/dimension values
- substantive claims (non-`corpus_limitation`) must carry evidence references
- dimension-section evidence ids belong to the correct cell via
  `_jurisdiction_evidence_ids(jurisdiction, dimension)`
- no orphan evidence references anywhere (sections, comparative blocks,
  patterns, synthesis)
- research-gap references resolve in `discover_gaps()` and belong to the cell
- research guidance resolves and touches the case
- the traceability manifest exactly matches the evidence actually referenced

## What the framework does NOT claim

- It is **not** the final academic paper; it is draft material with full
  traceability for the writing phase.
- It assigns no scores and no rankings.
- `missing_evidence` and gaps are about the corpus, not about a jurisdiction.
- Contradictions are listed, not silently resolved.
- No causal claims are made from cross-dimension co-occurrence.

## Data model

```json
{
  "narrative_type": "case_study_narrative",
  "schema_version": 1,
  "note": "...",
  "case": { "jurisdiction": "Ethiopia", "evidence_count": 26, "..." },
  "coverage_summary": { "supported": 10, "partial": 1, "missing_evidence": 1, "conflicting": 0 },
  "dimension_sections": [
    {
      "section_id": "ETHIOPIA-data_governance",
      "dimension": "data_governance",
      "evidence_status": "supported",
      "narrative": [
        { "claim_id": "ETHIOPIA-data_governance-claim-01",
          "statement": "Supported by evidence: ...",
          "statement_origin": "evidence_derived",
          "evidence_ids": [1, 19] }
      ],
      "research_gap_refs": []
    }
  ],
  "comparative_sections": [
    { "section_id": "ETHIOPIA-...-comparative-01", "pair": ["Ethiopia", "Kenya"], "narrative": [...] }
  ],
  "cross_cutting_patterns": [...],
  "synthesis": { "major_supported_findings": [...], "missing_evidence_areas": [...], "..." },
  "research_guidance": [
    { "gap_id": "KENYA-consent_individual_agency-source_diversity",
      "priority_level": "high",
      "research_question": "Which independent second source ...?" }
  ],
  "traceability": [
    { "evidence_id": 1, "section_id": "ETHIOPIA-data_governance",
      "dimension": "data_governance", "source_id": 2, "claim": "..." }
  ],
  "limitations": [...]
}
```

## Using the narrative for final writing

1. Generate the draft (`--validate --format markdown`).
2. Compose prose from the claim sentences; keep each statement's
   `[ev ...]` citations.
3. Where the draft says `[no evidence]` / `corpus_limitation`, reflect the
   limitation honestly rather than converting it into a verdict.
4. Use `comparative_sections` for cross-case discussion and `research_guidance`
   to state what still needs evidence.
5. Finish each section by checking the `traceability` manifest so every sentence
   retains at least one evidence anchor.