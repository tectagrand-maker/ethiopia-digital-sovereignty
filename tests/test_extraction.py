import os

import pytest

from src.evidence.extraction import extract_text


def _write(tmp_path, name, content, mode="w", encoding="utf-8"):
    path = os.path.join(str(tmp_path), name)
    with open(path, mode, encoding=encoding) as f:
        f.write(content)
    return path


def _make_pdf(tmp_path, text="Hello from a generated PDF", page2=None):
    """Build a tiny one/two-page PDF with extractable text.

    A minimal PDF with correct xref offsets is written by hand so the test does
    not depend on a PDF-generation library and the text is genuinely embedded.
    """
    texts = [text]
    if page2 is not None:
        texts.append(page2)
    n = len(texts)
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + 3*i} 0 R" for i in range(n))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, t in enumerate(texts):
        base = 3 + 3 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {base+1} 0 R /Resources << /Font << /F1 {base+2} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({t}) Tj ET".encode()
        objs.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    total = len(objs)
    out_bytes = b"%PDF-1.4\n"
    offsets = []
    for i, o in enumerate(objs):
        offsets.append(len(out_bytes))
        out_bytes += f"{i+1} 0 obj\n".encode() + o + b"\nendobj\n"
    xref_pos = len(out_bytes)
    out_bytes += f"xref\n0 {total+1}\n".encode()
    out_bytes += b"0000000000 65535 f \n"
    for off in offsets:
        out_bytes += f"{off:010d} 00000 n \n".encode()
    out_bytes += f"trailer\n<< /Size {total+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()

    out = os.path.join(str(tmp_path), "_gen_test.pdf")
    with open(out, "wb") as f:
        f.write(out_bytes)
    return out


def test_extraction_txt(tmp_path):
    p = _write(tmp_path, "t.txt", "plain text content")
    r = extract_text(p, source_id=42)
    assert r["status"] == "ok"
    assert r["text"] == "plain text content"
    assert r["source_id"] == 42
    assert r["content_type"] == "text/plain"


def test_extraction_html(tmp_path):
    p = _write(tmp_path, "t.html", "<html><body><p>Hello</p><p>World</p></body></html>")
    r = extract_text(p)
    assert r["status"] == "ok"
    assert "Hello" in r["text"]
    assert "World" in r["text"]
    assert "p>" not in r["text"]


def test_extraction_pdf(tmp_path):
    p = _make_pdf(tmp_path, "PDF TEXT UNIQUE MARKER")
    r = extract_text(p, source_id=7)
    assert r["status"] == "ok"
    assert "PDF TEXT UNIQUE MARKER" in r["text"]
    assert r["content_type"] == "application/pdf"
    assert isinstance(r["pages"], list)
    assert len(r["pages"]) >= 1


def test_extraction_pdf_preserves_page_boundaries(tmp_path):
    p = _make_pdf(tmp_path, "MARKER PAGE ONE", page2="MARKER PAGE TWO")
    r = extract_text(p, source_id=7)
    assert len(r["pages"]) == 2
    assert "MARKER PAGE ONE" in r["pages"][0]
    assert "MARKER PAGE TWO" in r["pages"][1]


def test_extraction_unsupported_file_type(tmp_path):
    p = _write(tmp_path, "t.xyz", "nope")
    with pytest.raises(NotImplementedError):
        extract_text(p)


def test_extraction_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text("data/processed/does_not_exist.txt")


def test_extraction_metadata(tmp_path):
    p = _write(tmp_path, "t2.txt", "meta")
    r = extract_text(p, source_id=3)
    assert r["extractor"] == "eds.extraction"
    assert r["extractor_version"]
    assert r["extracted_at"]
    assert r["sha256"]
    assert "text/plain" == r["content_type"]
