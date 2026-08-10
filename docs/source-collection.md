# Source Collection

This document explains how sources enter the research system, from discovery to
verified acquisition, and how their integrity is preserved.

## Source registry

The `Source` model is the registry of research sources *before* evidence is
extracted. Fields include title, source_type, publisher/author, publication
date, jurisdiction, jurisdiction_group (`ethiopia | comparative | international`),
institution, URL, language, access date, description, status, priority, research
domains, and data status.

A source record is **metadata only**. It does not assert anything about what the
source proves.

## Priority vs evidence strength

- `research_priority` (`high | medium | low`) = how urgently we want to
  investigate a source.
- `evidence_strength` = how strongly a source supports a particular claim.

These are different concepts and must never be confused.

## Source status workflow

```
discovered
  ↓
queued
  ↓
accessed
  ↓
extracted
  ↓
verified
  ↓
rejected / archived
```

`verified` means the metadata/source integrity has been checked — it does **not**
mean the source's claims are true or important.

## Acquisition

`acquire_source(source_id)` downloads exactly one user-selected public URL into
`data/raw/<source_id>/`. It is deliberately conservative:

- no crawling of whole sites;
- respects HTTP errors, and does not bypass robots rules, authentication,
  paywalls, or rate limits;
- records `retrieved_at`, `content_type`, `file_size` and `sha256`.

Alternatively, `save_raw_source(source_id, path)` stores a locally supplied file.

## Raw source storage policy

- Raw files live in `data/raw/<source_id>/`.
- `provenance.json` records: source_id, original_url, retrieved_at, filename,
  content_type, file_size, sha256.
- Large or copyrighted documents are **not** committed to git by default. The
  catalog and database remain portable even if raw files are excluded.
- Raw files are stored read-only and never modified.

## Text extraction

`extract_text(path, source_id=...)` returns structured metadata:

- `text`, `pages` (PDF page boundaries), `content_type`
- `extractor`, `extractor_version`, `extracted_at`
- `sha256`
- `status`: `ok` | `text_extraction_unavailable`

Supported formats: TXT, HTML, PDF. PDF extraction uses `pypdf`. Image-only /
scanned PDFs yield `text_extraction_unavailable` (OCR is **not** implemented and
is not claimed).

## Source → evidence distinction

- A `Source` says nothing about what it proves.
- Evidence is extracted by a researcher from the acquired text, with an exact
  locator and a source excerpt.
- Evidence is always linked to its source.

## Ethical / legal collection boundaries

Only sources explicitly selected by the researcher are acquired. We do not crawl
websites, bypass access controls, or download collections automatically. We
respect copyright, terms of service, and paywalls.
