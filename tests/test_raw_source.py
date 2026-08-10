import hashlib
import json
import os

import src.evidence.collection as collection
from src.evidence.collection import save_raw_source, verify_raw_source, add_source


def _make_file(path, content=b"hello raw source"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
    return path


def test_raw_file_storage():
    src = add_source({"title": "T", "source_type": "law", "publisher_or_author": "A",
                      "publication_date": "2024-01-01", "jurisdiction": "ET",
                      "url": "https://example.com/x"})
    src_path = _make_file(os.path.join(str(collection.RAW_ROOT), "tmp_src.txt"))
    dest, sha = save_raw_source(src.source_id, src_path)
    assert os.path.exists(dest)
    assert os.path.exists(os.path.join(collection.RAW_ROOT, str(src.source_id), "provenance.json"))


def test_sha256_generation_and_provenance():
    src = add_source({"title": "T", "source_type": "law", "publisher_or_author": "A",
                      "publication_date": "2024-01-01", "jurisdiction": "ET",
                      "url": "https://example.com/y"})
    content = b"deterministic bytes 123"
    src_path = _make_file(os.path.join(str(collection.RAW_ROOT), "tmp_src2.txt"), content)
    dest, sha = save_raw_source(src.source_id, src_path)
    assert sha == hashlib.sha256(content).hexdigest()

    prov_path = os.path.join(collection.RAW_ROOT, str(src.source_id), "provenance.json")
    with open(prov_path, "r", encoding="utf-8") as f:
        prov = json.load(f)
    assert prov["sha256"] == sha
    assert prov["file_size"] == len(content)
    assert "retrieved_at" in prov
    assert "filename" in prov


def test_integrity_verification_verified():
    src = add_source({"title": "T", "source_type": "law", "publisher_or_author": "A",
                      "publication_date": "2024-01-01", "jurisdiction": "ET",
                      "url": "https://example.com/z"})
    src_path = _make_file(os.path.join(str(collection.RAW_ROOT), "tmp_src3.txt"))
    save_raw_source(src.source_id, src_path)
    assert verify_raw_source(src.source_id) == "verified"


def test_integrity_verification_mismatch():
    src = add_source({"title": "T", "source_type": "law", "publisher_or_author": "A",
                      "publication_date": "2024-01-01", "jurisdiction": "ET",
                      "url": "https://example.com/w"})
    src_path = _make_file(os.path.join(str(collection.RAW_ROOT), "tmp_src4.txt"))
    save_raw_source(src.source_id, src_path)

    # Tamper with the stored raw file.
    stored = os.path.join(collection.RAW_ROOT, str(src.source_id), "tmp_src4.txt")
    with open(stored, "ab") as f:
        f.write(b"tampered")
    assert verify_raw_source(src.source_id) == "INTEGRITY_MISMATCH"


def test_integrity_verification_no_raw_file():
    src = add_source({"title": "T", "source_type": "law", "publisher_or_author": "A",
                      "publication_date": "2024-01-01", "jurisdiction": "ET",
                      "url": "https://example.com/v"})
    assert verify_raw_source(src.source_id) == "no_raw_file"


