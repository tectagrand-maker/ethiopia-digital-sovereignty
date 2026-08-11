# Research Gaps (Step 6)

This document records where the current corpus does **not** yet support an
evidence-based assessment. A gap is a statement about the corpus, never a
negative finding about Ethiopia (or any other jurisdiction).

> **Step 9**: the reproducible, machine-readable gap framework — discovery,
> classification, prioritization, research actions and evidence-expansion
> guidance — lives in `docs/research-gap-framework.md` and is generated with
> `python -m src.cli research-gaps`. This page documents the current corpus
> gaps that the Step 9 framework derives from.

## Dimensions with no evidence

Three of the twelve governance dimensions currently have no real evidence
records for Ethiopia:

- `transparency`
- `interoperability`
- `private_sector_dependence`

These remain `missing_evidence` in `research-matrix` output. Useful source
candidates to close them:

- **transparency**: ECA Communications Proclamation 1148/2019 (transparency of
  the regulator), freedom-of-information instruments, PDP 1321/2024 transparency
  of processing provisions.
- **interoperability**: Digital Ethiopia 2025 interoperability pillars, e-Transact
  Proclamation 1205/2020 data-sharing provisions, government interoperability
  framework documentation.
- **private_sector_dependence**: World Bank/ID4D financing structures for Fayda,
  private vendors in the digital ID supply chain, telecom sector market
  structure.

## Sources acquired but not yet extracted into evidence

Source 11 (AU Malabo Convention) was acquired but its PDFs are image-only;
extraction is flagged `text_extraction_unavailable` (OCR is out of scope). The
au.int HTML landing page is available but provides limited normative text.

## Sources still `discovered`

Sources 6, 7, 14, 15, 16 in the catalog are discovered but not yet accessed:

- Source 7 (Fayda / NIDP portal) could not be acquired due to an SSL
  certificate verification failure (self-signed certificate). Needs a different
  acquisition route or an alternative canonical URL.
- Sources 6, 14, 15, 16 were not scheduled for acquisition in Step 6.

## Time-bound evidence

Some evidence is time-limited and must not be read as a current state:

- **UNECA country profile (early 2024)**: recorded that Ethiopia lacked a
  comprehensive personal data protection law. The Personal Data Protection
  Proclamation No. 1321/2024 was gazetted **24 July 2024**, after that report.
  The relation between the UNECA evidence and the PDP evidence is recorded as
  `contextualizes` (see `evidence relations` below).
- **World Bank registration figures (Dec 2023)**: "more than 3.5 million"
  Fayda pilot registrations are the financier's stated figure as of the press
  release date; they are not an independent audit and are not evidence of the
  current enrollment level.

## Contradictions

There are currently **no unresolved `contradicts` relations** in the corpus.
The main tension to watch is temporal rather than contradictory: UNECA's
"no comprehensive law as of early 2024" versus the 2024 PDP. This is recorded
as a `contextualizes` relation rather than a contradiction because both
statements are accurate for their respective dates.

## Legal vs implementation gap

The Ethiopia corpus is dominated by `normative` evidence (statutes) plus a small
number of `institutional` and `observational`/`implementation` records. There is
little independent implementation evidence for: enforcement of PDP 1321/2024,
the ECA's operational capacity as supervisory authority, and Fayda grievance
resolution outcomes. Closing this gap requires field-level or evaluative
sources, not additional statute text.

## Verification

`python -m src.cli research-status` reports the live gap state:

- `governance.dimensions_with_missing_evidence`
- `gaps.sources_without_evidence`
- `gaps.unresolved_contradictions`

## Comparator gaps (Step 7)

The comparative layer (`python -m src.cli comparative`) surfaces the same
corpus-level gaps per case. In the current corpus:

- **Kenya** has 4 evidence records (consent, rights, ODPC, cross-border
  transfer) — every other dimension cell is `missing_evidence`.
- **European Union (GDPR)** has 2 evidence records (consent definition,
  supervisory authorities) — likewise mostly `missing_evidence`.
- Because most comparator cells are empty, the pairwise comparison notes
  default to `insufficient_evidence` or `not_comparable` for those dimensions;
  this is an accurate reflection of the corpus, not a finding about those
  jurisdictions.

Closing these gaps requires acquiring and extracting comparator sources for
the missing dimensions (for example Kenya's digital identity and cybersecurity
frameworks, and GDPR data-localization/transfer provisions beyond s.48).
