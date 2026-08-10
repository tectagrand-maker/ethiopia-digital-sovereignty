import json
import csv
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError
from src.evidence.models import (
    Evidence, Source, SourceType, DataStatus,
    EvidenceBasis, GOVERNANCE_DIMENSIONS, RESEARCH_DOMAINS,
)

LOCATOR_TYPES = {
    'page', 'section', 'paragraph', 'table', 'figure',
    'url_fragment', 'timestamp', 'line_range', 'other',
}


class EvidenceSchema(BaseModel):
    title: str
    source_type: str
    publisher_or_author: str
    publication_date: Optional[date] = None
    country_or_jurisdiction: str
    institution: Optional[str] = None
    domain_theme: str
    claim: str
    evidence_summary: str
    source_excerpt: Optional[str] = None
    interpretation: Optional[str] = None
    source_url: Optional[str] = None
    citation: Optional[str] = None
    reliability_level: int = Field(..., ge=1, le=5)
    evidence_strength: int = Field(..., ge=1, le=5)
    methodology_or_basis: Optional[str] = None
    evidence_basis: Optional[str] = None
    relevant_policy_or_law: Optional[str] = None
    keywords: Optional[str] = None
    notes: Optional[str] = None
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    data_status: str = DataStatus.REAL.value

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v):
        if v not in {e.value for e in SourceType}:
            raise ValueError(f"Invalid source type: {v}. Must be one of {sorted(e.value for e in SourceType)}")
        return v

    @field_validator('data_status')
    @classmethod
    def validate_data_status(cls, v):
        if v not in {e.value for e in DataStatus}:
            raise ValueError(f"Invalid data_status: {v}. Must be one of {sorted(e.value for e in DataStatus)}")
        return v

    @field_validator('locator_type')
    @classmethod
    def validate_locator_type(cls, v):
        if v is not None and v not in LOCATOR_TYPES:
            raise ValueError(f"Invalid locator_type: {v}. Must be one of {sorted(LOCATOR_TYPES)}")
        return v

    @field_validator('domain_theme')
    @classmethod
    def validate_domain_theme(cls, v):
        if v not in RESEARCH_DOMAINS:
            raise ValueError(
                f"Invalid domain_theme: {v}. Use one of the controlled research domains: {RESEARCH_DOMAINS}"
            )
        return v

    @field_validator('evidence_basis')
    @classmethod
    def validate_evidence_basis(cls, v):
        if v is not None and v not in {e.value for e in EvidenceBasis}:
            raise ValueError(
                f"Invalid evidence_basis: {v}. Must be one of {sorted(e.value for e in EvidenceBasis)}"
            )
        return v


def ingest_evidence(record_data: dict, source_id: int):
    """Validate and insert a single evidence record linked to a source.

    Returns the created Evidence row, or raises ValueError on validation/source
    failure so callers can report exact record-level errors.
    """
    try:
        validated_record = EvidenceSchema(**record_data)
    except ValidationError as e:
        raise ValueError(f"Validation failed: {e}")

    source = Source.get_or_none(Source.source_id == source_id)
    if not source:
        raise ValueError(f"Source ID {source_id} not found.")

    query = Evidence.select().where(
        (Evidence.source == source) & (Evidence.title == validated_record.title)
    )
    if query.exists():
        raise ValueError(f"Duplicate evidence detected: {validated_record.title} (already linked to source {source_id})")

    data = validated_record.model_dump()
    data['source'] = source
    return Evidence.create(**data)


def import_from_json(json_file_path: str, source_id: int):
    return _import_records(json.load(open(json_file_path, 'r', encoding='utf-8')), source_id)


def import_from_csv(csv_file_path: str, source_id: int):
    records = []
    with open(csv_file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = dict(row)
            for k in ('reliability_level', 'evidence_strength'):
                if k in rec and rec[k] not in (None, ''):
                    rec[k] = int(rec[k])
                else:
                    rec[k] = None
            if rec.get('publication_date') in (None, ''):
                rec['publication_date'] = None
            records.append(rec)
    return _import_records(records, source_id)


def _import_records(records, source_id):
    summary = {"read": 0, "accepted": 0, "rejected": 0, "duplicates": 0, "errors": []}
    for idx, record in enumerate(records, start=1):
        summary["read"] += 1
        try:
            ingest_evidence(record, source_id)
            summary["accepted"] += 1
        except ValueError as e:
            message = str(e)
            if "Duplicate" in message:
                summary["duplicates"] += 1
            else:
                summary["rejected"] += 1
            summary["errors"].append({"record": idx, "reason": message})
    return summary
