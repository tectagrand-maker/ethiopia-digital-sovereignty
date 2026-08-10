# Comparative Analysis

The comparative layer compares jurisdictions or systems across 12 governance
dimensions, using only evidence that has actually been recorded.

## Governance dimensions

Stable machine-readable identifiers:

| Identifier | Dimension |
|---|---|
| `data_governance` | Data governance |
| `digital_identity` | Digital identity |
| `consent_individual_agency` | Consent and individual agency |
| `data_localization` | Data localization / jurisdiction |
| `institutional_accountability` | Institutional accountability |
| `transparency` | Transparency |
| `interoperability` | Interoperability |
| `state_capacity` | State capacity / institutional control |
| `private_sector_dependence` | Private-sector dependence |
| `security_resilience` | Security and resilience |
| `legal_regulatory_safeguards` | Legal/regulatory safeguards |
| `citizen_rights_redress` | Citizen rights and redress |

## Observations

A `GovernanceObservation` records, for a jurisdiction/system and dimension:

- `indicator`
- `observed_evidence`
- `assessment`
- `confidence` (integer 1-5, or null)
- `analytical_notes`
- one or more linked `evidence_ids` (validated — a broken reference is rejected)

## Evidence references

Every observation must reference real evidence IDs. The evidence reference is a
many-to-many relationship (`EvidenceObservation`), so one observation can cite
multiple pieces of evidence and one piece of evidence can support multiple
observations.

## Missing evidence

A dimension with no recorded observation is reported as:

```
"status": "missing_evidence"
"assessment": null
"confidence": null
```

**Missing evidence is NOT a negative assessment.** We never output `weak`,
`poor`, `low`, or a numerical score simply because data is absent. Absence of
evidence is not evidence of absence.

## Comparison output

`get_comparative_data(j1, j2)` returns deterministic, machine-readable output
for all 12 dimensions:

```json
{
  "comparison": {
    "jurisdiction_a": "Ethiopia",
    "jurisdiction_b": "ExampleSystem"
  },
  "dimensions": [
    {
      "dimension": "data_governance",
      "Ethiopia": {
        "status": "evidence_available",
        "assessment": ["..."],
        "confidence": [4],
        "observations": [ ... ],
        "evidence_ids": [1]
      },
      "ExampleSystem": {
        "status": "missing_evidence",
        "assessment": null,
        "confidence": null,
        "observations": [],
        "evidence_ids": []
      }
    }
  ]
}
```

`comparison_to_json(data)` and `comparison_to_csv(data)` serialize the same
structure.

## Confidence

Confidence reflects the evidence base supporting an assessment. It is
researcher-assigned and should be consistent with the reliability/strength of
the underlying evidence. If there is no evidence, confidence is null.

## Distinguishing real from synthetic

Comparisons never blend real and synthetic data invisibly. Every observation and
evidence record carries `data_status` (`real | synthetic | methodological`), and
the output exposes it so a researcher can separate demonstration fixtures from
real findings.

## Comparative governance analysis (Step 7)

`src/governance/comparison.py` extends the pairwise comparison into a
reproducible, multi-case analysis across the same 12 dimensions.

```bash
python -m src.cli comparative                      # all available cases
python -m src.cli comparative --cases Ethiopia,Kenya,EU --format json
python -m src.cli comparative --cases Ethiopia,Kenya --format csv
python -m src.cli comparative --validate           # schema-check before printing
```

Cases are any jurisdiction with at least one real evidence record or real
observation (e.g. Ethiopia, Kenya, European Union in the current corpus).
Output is deterministic: cases are sorted, dimensions keep the fixed order, and
comparison notes are sorted.

### Explicit categories

Every `(case, dimension)` cell distinguishes five things:

| category | field | meaning |
|---|---|---|
| supported evidence | `evidence_status` | `supported` (>=2 evidence, >=2 sources) or `partial` (>=1) |
| missing evidence | `evidence_status` | `missing_evidence` when the cell has no real evidence |
| conflicting evidence | `evidence_status` / `conflicts` | `conflicting` when linked evidence carries a `contradicts` relation; the pairs are listed |
| analytical interpretation | `interpretation` / `analytical_notes` | the assessment text from linked governance observations |
| research gaps | `gaps` | structured gap note for the cell |

### Evidence traceability

Each cell's `evidence` list is fully traceable to the underlying provenance:
`evidence_id`, `source_id`, `source_title`, `source_type`, `locator_type` /
`locator_value`, `claim`, `evidence_basis`, `data_status`, `citation` and
`source_url`. Nothing in the report is invented: every claim, assessment and gap
originates from committed evidence, observations or the defined status rules.

### Interpretation limits

- The report is **not a ranking** and never assigns scores.
- `missing_evidence` is a statement about the corpus, not a negative assessment.
- `conflicting` means the corpus contains recorded contradictions; the report
  lists them rather than silently resolving them.
- Pairwise `comparison_notes` reuse the Step 6 baseline heuristic, which
  classifies patterns from evidence *confidence*. Read the `interpretation`
  text alongside each note; the note is methodological, not substantive.
- Evidence basis (`normative`, `institutional`, `implementation`, ...) is
  reported per record; a law-on-paper record is never presented as evidence of
  enforcement.

### Schema and integrity

`validate_report()` checks the report against a pydantic schema: exactly the 12
dimensions, valid `evidence_status` values, and case keys that match the
report's case set. The CLI `--validate` flag runs this check before printing.
