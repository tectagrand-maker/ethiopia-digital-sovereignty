# Evidence Matrix (Step 6)

The evidence matrix reports, for each governance dimension, what the current
corpus can actually support. It is an **analytical research-coverage artifact,
not a governance scorecard**. `missing_evidence` means the corpus does not yet
provide sufficient evidence — it is not a negative assessment.

## Matrix outputs

Three CLI commands produce the matrix views:

```bash
python -m src.cli research-matrix --jurisdiction Ethiopia
python -m src.cli coverage-matrix --format csv
python -m src.cli baseline --j1 Ethiopia --j2 Kenya
```

### `research-matrix`

Per-dimension rows for one jurisdiction:

- `evidence_count`, `source_count`, `observation_count`
- `status` — derived from the evidence base (see below)
- `confidence` — average of the confidence of linked observations (or `null`)
- `evidence_ids`, `source_ids`, `key_supported_claims`, `major_gaps`

### `coverage-matrix`

A jurisdiction × 12-dimension grid (one row per cell) with evidence counts and
the derived status, exported to CSV.

### `baseline` (comparative)

`comparative_baseline(j1, j2)` classifies each dimension as:

- `similar_pattern` — both jurisdictions have evidence and comparable confidence
- `different_pattern` — both have evidence but confidence differs materially
  (>= 2 points on the 1-5 scale)
- `insufficient_evidence` — only one side has evidence
- `not_comparable` — neither side has evidence

The classification is a **methodological heuristic based on confidence**, not a
substantive verdict. Two jurisdictions can legitimately receive
`similar_pattern` while their assessments describe materially different legal
approaches (for example, Ethiopia's territorial data-storage mandate in PDP
Art. 22 versus Kenya's safeguards-based cross-border transfer regime in DPA
s.48 both rest on high-confidence statutory text). Always read the
`assessment` text alongside the `comparison_note`.

## Status derivation

| status | condition |
|---|---|
| `supported` | >= 2 real evidence records across >= 2 sources |
| `partial` | >= 1 real evidence record (single record or single source) |
| `missing_evidence` | no real evidence record |

## Evidence basis

Each evidence record is classified by what it can establish
(`evidence_basis`):

- `normative` — primary legal/policy text; what the law requires
- `institutional` — institutions, powers, organisational set-up
- `technical` — technical architecture, systems, standards
- `empirical` — observed data, studies, surveys, field findings
- `implementation` — descriptions of actual rollout, deployment, practice
- `observational` — on-the-ground observation / journalism / qualitative accounts

`evidence_basis` does **not** indicate how well a requirement is implemented.
For example, PDP 1321/2024 produces `normative` evidence of a comprehensive
data-protection framework while UNECA's country profile produces `empirical`
evidence of the pre-2024 legal gap; neither alone evidences operational
enforcement.

## Domain-to-dimension mapping

Evidence records carry a research `domain_theme`; observations carry one of the
12 governance dimensions. The coverage matrix maps domains onto dimensions:

| research domain | governance dimension |
|---|---|
| `data_governance`, `privacy` | `data_governance` |
| `digital_identity` | `digital_identity` |
| `consent` | `consent_individual_agency` |
| `cybersecurity` | `security_resilience` |
| `digital_public_infrastructure` | `state_capacity` |
| `interoperability` | `interoperability` |
| `institutional_accountability` | `institutional_accountability` |
| `citizen_rights` | `citizen_rights_redress` |
| `digital_sovereignty` | `data_localization` |

Observation links take precedence over the domain map when both exist. This is
a documented analytical convention, not a claim of equivalence.

## Ethiopia matrix (current corpus)

Built from `data/evidence/corpus/*.json` (see `corpus_manifest.json`):

| dimension | status | evidence | sources |
|---|---|---|---|
| `data_governance` | supported | 2 | 2 |
| `digital_identity` | supported | 3 | 2 |
| `consent_individual_agency` | supported | 5 | 4 |
| `data_localization` | partial | 1 | 1 |
| `institutional_accountability` | supported | 2 | 2 |
| `transparency` | missing_evidence | 0 | 0 |
| `interoperability` | missing_evidence | 0 | 0 |
| `state_capacity` | partial | 2 | 1 |
| `private_sector_dependence` | missing_evidence | 0 | 0 |
| `security_resilience` | supported | 3 | 2 |
| `legal_regulatory_safeguards` | supported | 3 | 3 |
| `citizen_rights_redress` | supported | 4 | 3 |

Generate the live numbers with `python -m src.cli research-matrix`.

## Contradictions and relations

Evidence relations (`supports`, `qualifies`, `contradicts`, `contextualizes`)
are recorded between evidence records without silently resolving conflicts.
Unresolved `contradicts` relations are surfaced in `research-status`
(`gaps.unresolved_contradictions`).
