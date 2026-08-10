import os
import io
import json
import datetime
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from src.evidence.models import Source, SourceStatus, DataStatus

RAW_ROOT = os.path.join('data', 'raw')


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _validate_url(url):
    """Raise ValueError for URLs that are clearly invalid (bad scheme or no host).

    Empty values are allowed (sources without a URL are legitimate).
    """
    if not url:
        return
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError(
            f"Invalid URL {url!r}: must be an http(s) URL with a host."
        )


def add_source(data: dict):
    """Create a source record (or return the existing one for identical URL).

    Deterministic duplicate detection uses the normalized URL when present;
    otherwise falls back to title + publisher/author + publication_date.
    """
    url = (data.get('url') or '').strip()
    _validate_url(url)
    existing = None
    if url:
        existing = Source.get_or_none(Source.url == url)
    if existing is None and data.get('title'):
        query = Source.select().where(
            Source.title == data['title'],
            Source.publisher_or_author == data.get('publisher_or_author', ''),
        )
        if data.get('publication_date'):
            query = query.where(Source.publication_date == data['publication_date'])
        existing = query.get_or_none()
    if existing is not None:
        return existing

    defaults = {
        'status': SourceStatus.DISCOVERED.value,
        'priority': 'medium',
        'research_priority': 'medium',
        'jurisdiction_group': 'ethiopia',
        'data_status': DataStatus.REAL.value,
    }
    defaults.update(data)
    return Source.create(**defaults)


def get_source(source_id: int):
    return Source.get_or_none(Source.source_id == source_id)


def list_sources(status=None, jurisdiction_group=None):
    query = Source.select()
    if status:
        query = query.where(Source.status == status)
    if jurisdiction_group:
        query = query.where(Source.jurisdiction_group == jurisdiction_group)
    return list(query)


def update_source_status(source_id: int, status: str):
    source = get_source(source_id)
    if not source:
        return False
    valid = {s.value for s in SourceStatus}
    if status not in valid:
        raise ValueError(f"Invalid status {status!r}. Must be one of {sorted(valid)}")
    source.status = status
    source.updated_at = datetime.datetime.now()
    source.save()
    return True


def acquire_source(source_id: int, url=None, headers=None):
    """Download a selected public source into data/raw/<source_id>/ and write provenance.json.

    Conservative by design: downloads exactly one user-selected URL, respects
    common HTTP error responses, and does not crawl or bypass access controls.
    """
    source = get_source(source_id)
    if not source:
        raise ValueError("Source not found")
    target_url = url or source.url
    if not target_url:
        raise ValueError("No URL available for this source")

    req = urllib.request.Request(target_url, headers=headers or {
        'User-Agent': 'ethiopia-digital-sovereignty/0.1 (research; contact: research@example.com)'
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        content_type = resp.headers.get('Content-Type', 'application/octet-stream')

    filename = os.path.basename(target_url.split('?')[0]) or f"source_{source_id}"
    if not os.path.splitext(filename)[1]:
        ext = '.html' if 'text/html' in content_type else '.pdf' if 'application/pdf' in content_type else ''
        filename = filename + ext

    raw_dir = os.path.join(RAW_ROOT, str(source_id))
    os.makedirs(raw_dir, exist_ok=True)
    dest_path = os.path.join(raw_dir, filename)
    with open(dest_path, 'wb') as f:
        f.write(raw)

    sha256 = hashlib.sha256(raw).hexdigest()
    provenance = {
        "source_id": source_id,
        "original_url": target_url,
        "retrieved_at": _now(),
        "filename": filename,
        "content_type": content_type,
        "file_size": len(raw),
        "sha256": sha256,
    }
    with open(os.path.join(raw_dir, 'provenance.json'), 'w', encoding='utf-8') as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)

    source.status = SourceStatus.ACCESSED.value
    source.access_date = datetime.date.today()
    source.updated_at = datetime.datetime.now()
    source.save()

    return provenance


def save_raw_source(source_id: int, file_path: str):
    """Store a locally supplied raw file under data/raw/<source_id>/ with provenance."""
    source = get_source(source_id)
    if not source:
        raise ValueError("Source not found")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, 'rb') as f:
        raw = f.read()

    raw_dir = os.path.join(RAW_ROOT, str(source_id))
    os.makedirs(raw_dir, exist_ok=True)
    dest_path = os.path.join(raw_dir, os.path.basename(file_path))
    with open(dest_path, 'wb') as f:
        f.write(raw)

    sha256 = hashlib.sha256(raw).hexdigest()
    provenance = {
        "source_id": source_id,
        "original_url": source.url,
        "retrieved_at": _now(),
        "filename": os.path.basename(file_path),
        "content_type": "application/octet-stream",
        "file_size": len(raw),
        "sha256": sha256,
    }
    with open(os.path.join(raw_dir, 'provenance.json'), 'w', encoding='utf-8') as f:
        json.dump(provenance, f, indent=2, ensure_ascii=False)

    source.status = SourceStatus.ACCESSED.value
    source.updated_at = datetime.datetime.now()
    source.save()

    return dest_path, sha256


def verify_raw_source(source_id: int):
    """Verify the stored raw file against the recorded SHA-256.

    Returns one of: 'verified' | 'INTEGRITY_MISMATCH' | 'no_raw_file'
    """
    raw_dir = os.path.join(RAW_ROOT, str(source_id))
    provenance_path = os.path.join(raw_dir, 'provenance.json')
    if not os.path.exists(provenance_path):
        return "no_raw_file"

    with open(provenance_path, 'r', encoding='utf-8') as f:
        provenance = json.load(f)

    raw_path = os.path.join(raw_dir, provenance['filename'])
    if not os.path.exists(raw_path):
        return "no_raw_file"

    current_hash = hashlib.sha256(open(raw_path, 'rb').read()).hexdigest()
    if current_hash == provenance['sha256']:
        return "verified"
    return "INTEGRITY_MISMATCH"


def import_source_manifest(manifest_path):
    """Import a source registry manifest (JSON list of source metadata).

    Returns a dict summary: {read, accepted, rejected, duplicates, errors}.
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    summary = {"read": 0, "accepted": 0, "rejected": 0, "duplicates": 0, "errors": []}
    if not isinstance(records, list):
        raise ValueError("Manifest must be a JSON list of source objects")

    for idx, record in enumerate(records, start=1):
        summary["read"] += 1
        if not isinstance(record, dict) or not record.get('title'):
            summary["rejected"] += 1
            summary["errors"].append({"record": idx, "reason": "missing required 'title'"})
            continue

        url = (record.get('url') or '').strip()
        dup = None
        if url:
            dup = Source.get_or_none(Source.url == url)
        if dup is None and record.get('publisher_or_author'):
            dup = Source.get_or_none(
                Source.title == record['title'],
                Source.publisher_or_author == record['publisher_or_author'],
            )

        if dup is not None:
            summary["duplicates"] += 1
            continue
        add_source(record)
        summary["accepted"] += 1

    return summary
