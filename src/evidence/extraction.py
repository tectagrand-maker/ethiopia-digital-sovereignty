import os
import hashlib
import datetime

EXTRACTOR_VERSION = "1.0.0"

SUPPORTED_EXTENSIONS = ('.txt', '.html', '.htm', '.pdf')


def _sha256_of_file(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def _extract_txt(file_path, encoding='utf-8'):
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()


def _extract_html(file_path):
    from html.parser import HTMLParser

    class TagStripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.data = []

        def handle_data(self, data):
            self.data.append(data)

    parser = TagStripper()
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        parser.feed(f.read())
    return " ".join(part.strip() for part in parser.data if part.strip())


def _extract_pdf(file_path):
    """Extract text from a PDF, preserving page boundaries where available.

    If the PDF yields no extractable text (e.g. scanned/image-only pages), the
    result is flagged as ``text_extraction_unavailable`` rather than pretending
    extraction succeeded. OCR is NOT implemented.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise NotImplementedError(
            "PDF extraction requires the 'pypdf' package. Install with: "
            "pip install pypdf"
        )

    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        pages.append(page_text)

    full_text = "\n\n".join(pages).strip()
    if not full_text:
        return None, pages, "text_extraction_unavailable"
    return full_text, pages, "ok"


def extract_text(file_path, source_id=None):
    """Extract text from a raw source file and return structured provenance.

    Returns a dict with:
      - source_id, file_path, content_type
      - text (full extracted text), pages (list, PDF only, may be None)
      - extractor, extractor_version, extracted_at, sha256
      - status: 'ok' | 'text_extraction_unavailable'

    The raw file is never modified.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    content_type = {
        '.txt': 'text/plain',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.pdf': 'application/pdf',
    }.get(ext, 'application/octet-stream')

    sha256 = _sha256_of_file(file_path)
    extracted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    result = {
        "source_id": source_id,
        "file_path": os.path.abspath(file_path),
        "content_type": content_type,
        "text": None,
        "pages": None,
        "extractor": "eds.extraction",
        "extractor_version": EXTRACTOR_VERSION,
        "extracted_at": extracted_at,
        "sha256": sha256,
        "status": None,
    }

    if ext == '.txt':
        result["text"] = _extract_txt(file_path)
        result["status"] = "ok"
    elif ext in ('.html', '.htm'):
        result["text"] = _extract_html(file_path)
        result["status"] = "ok"
    elif ext == '.pdf':
        text, pages, status = _extract_pdf(file_path)
        result["text"] = text
        result["pages"] = pages
        result["status"] = status
    else:
        raise NotImplementedError(f"Unsupported file type: {ext}")

    return result
