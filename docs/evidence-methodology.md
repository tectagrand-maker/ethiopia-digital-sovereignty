# Evidence Methodology

This project is designed for **auditable research** rather than unsupported
assertions. The central discipline is a strict separation between distinct
concepts that are too often collapsed into a single free-text field.

## The distinction chain

```
SOURCE
  → EVIDENCE
  → CLAIM
  → INTERPRETATION
  → ASSESSMENT
  → CONFIDENCE
```

### Source

The raw document or record (a law, regulation, report, webpage, dataset). A
`Source` record holds verifiable metadata only: title, publisher/author,
publication date, jurisdiction, institution, URL, access date, status, priority,
research domains. It says nothing yet about what the source "proves".

### Evidence

A structured representation of what a source supports: a passage located in the
source (`source_excerpt`), a `locator` (page, section, paragraph, table,
timestamp...), and linkage to the `Source` and to the stored raw file (with
SHA-256). Evidence records carry `reliability_level` and `evidence_strength`.

### Claim

The proposition that the evidence is used to support. Claims are researcher-
entered. The software does **not** auto-generate claims from text.

### Interpretation

The researcher's analytical reading of the evidence. Always kept separate from
`source_excerpt` (what the source actually says) and from `evidence_summary`
(the structured summary).

### Assessment

A structured governance evaluation for a jurisdiction/system and dimension,
recorded in a `GovernanceObservation`. Observations must reference at least one
valid evidence ID.

### Confidence

How strongly the available evidence supports the assessment (integer 1-5, or
null when there is no basis). Confidence is about the evidence base, not about
political or normative preference.

## Provenance

Every evidence record is traceable:

```
Evidence ID
  → Source ID
  → Source metadata
  → Raw source file (data/raw/<source_id>/)
  → SHA-256
  → Locator
  → Source excerpt
```

A researcher can audit an analytical claim back to the exact location in the
stored, hash-verified raw source.

## Integrity hashes

When a raw source is stored, a SHA-256 hash is recorded in `provenance.json`.
`verify_raw_source(source_id)` recomputes the hash and compares it. A mismatch
returns `INTEGRITY_MISMATCH`; the hash is never silently updated.

## Duplicate handling

Deterministic, conservative:

- by normalized URL when present;
- otherwise by title + publisher/author + publication date.

No fuzzy matching that could wrongly merge distinct sources.

## Missing evidence and uncertainty

- Missing evidence is reported as `missing_evidence`.
- **Never** convert absence of evidence into evidence of absence ("no evidence
  of X therefore X is weak/absent"). No score is invented for a missing value.
- A governance observation without evidence references is rejected unless
  explicitly marked `methodological`.

## Why unsupported conclusions are prohibited

This platform is meant to be auditable. Every assessment should eventually trace
back to evidence records, sources, and exact source locations. If a conclusion
cannot be traced this way, it has no place in the database.

## Real vs synthetic data

Every record carries `data_status`:

- `real` — verifiable source/evidence collected during research;
- `synthetic` — clearly labelled demonstration data, never presented as findings;
- `methodological` — structural/analytical scaffolding, not source-based.

Demo fixtures must always be labelled `synthetic`. Real and synthetic records
are never blended invisibly in comparisons.
