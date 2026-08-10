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
