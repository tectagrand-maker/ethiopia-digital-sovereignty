import os

import pytest

from src.evidence.models import Source
from src.evidence.collection import add_source, get_source, list_sources, update_source_status


def _src(overrides=None):
    data = {
        "title": "Test Source",
        "source_type": "law",
        "publisher_or_author": "Agency",
        "publication_date": "2024-01-01",
        "jurisdiction": "Ethiopia",
        "url": "https://example.com/law",
    }
    data.update(overrides or {})
    return data


def test_source_metadata_validation():
    """Source creation persists required metadata."""
    s = add_source(_src())
    assert s.source_id is not None
    row = get_source(s.source_id)
    assert row.title == "Test Source"
    assert row.source_type == "law"
    assert row.jurisdiction == "Ethiopia"
    assert row.jurisdiction_group == "ethiopia"


def test_source_url_validation():
    """Invalid URLs are rejected, not silently stored."""
    with pytest.raises(ValueError):
        add_source(_src({"url": "not-a-url"}))
    with pytest.raises(ValueError):
        add_source(_src({"url": "ftp://example.com/file"}))


def test_source_url_validation_accepts_blank():
    """A source without a URL is legitimate."""
    s = add_source(_src({"url": None}))
    assert s.source_id is not None


def test_source_deduplication_by_url():
    """Adding the same URL twice returns the existing record."""
    s1 = add_source(_src())
    s2 = add_source(_src())
    assert s1.source_id == s2.source_id


def test_source_deduplication_by_title_publisher():
    """Same title+publisher without URL is treated as a duplicate."""
    s1 = add_source(_src({"url": None}))
    s2 = add_source(_src({"url": None}))
    assert s1.source_id == s2.source_id


def test_source_status_workflow():
    """Source status can be advanced through the controlled lifecycle."""
    s = add_source(_src())
    assert s.status == "discovered"
    update_source_status(s.source_id, "queued")
    update_source_status(s.source_id, "accessed")
    update_source_status(s.source_id, "extracted")
    update_source_status(s.source_id, "verified")
    assert get_source(s.source_id).status == "verified"


def test_source_status_invalid_value_rejected():
    s = add_source(_src())
    with pytest.raises(ValueError):
        update_source_status(s.source_id, "not-a-status")


def test_source_retrieval_missing_returns_none():
    assert get_source(99999) is None


def test_source_listing_and_filtering():
    add_source(_src({"jurisdiction": "Ethiopia", "jurisdiction_group": "ethiopia", "url": "https://example.com/a"}))
    add_source(_src({"title": "Kenya Law", "jurisdiction": "Kenya", "jurisdiction_group": "comparative", "url": "https://example.com/b"}))
    eth = list_sources(jurisdiction_group="ethiopia")
    cmp = list_sources(jurisdiction_group="comparative")
    assert len(eth) == 1
    assert len(cmp) == 1
    assert eth[0].title == "Test Source"
