from peewee import *
import datetime
from enum import Enum

db = SqliteDatabase('data/evidence.db')

class SourceType(Enum):
    LAW = 'law'
    REGULATION = 'regulation'
    GOVERNMENT_DOCUMENT = 'government_document'
    POLICY = 'policy'
    COURT_DECISION = 'court_decision'
    ACADEMIC_PAPER = 'academic_paper'
    TECHNICAL_REPORT = 'technical_report'
    INSTITUTIONAL_REPORT = 'institutional_report'
    DATASET = 'dataset'
    OFFICIAL_WEBPAGE = 'official_webpage'
    CIVIL_SOCIETY_REPORT = 'civil_society_report'
    JOURNALISM = 'journalism'
    OTHER = 'other'

class SourceStatus(Enum):
    DISCOVERED = 'discovered'
    QUEUED = 'queued'
    ACCESSED = 'accessed'
    EXTRACTED = 'extracted'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    ARCHIVED = 'archived'

class DataStatus(Enum):
    """Distinguishes real research data from demonstration/synthetic records.

    - real:          verifiable source/evidence collected during research
    - synthetic:     clearly labelled demonstration data (never real findings)
    - methodological: structural/analytical scaffolding, not source-based
    """
    REAL = 'real'
    SYNTHETIC = 'synthetic'
    METHODOLOGICAL = 'methodological'

class ResearchPriority(Enum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

class JurisdictionGroup(Enum):
    ETHIOPIA = 'ethiopia'
    COMPARATIVE = 'comparative'
    INTERNATIONAL = 'international'

# Stable machine-readable governance dimension identifiers (see docs/comparative-analysis.md)
GOVERNANCE_DIMENSIONS = [
    "data_governance",
    "digital_identity",
    "consent_individual_agency",
    "data_localization",
    "institutional_accountability",
    "transparency",
    "interoperability",
    "state_capacity",
    "private_sector_dependence",
    "security_resilience",
    "legal_regulatory_safeguards",
    "citizen_rights_redress",
]

RESEARCH_DOMAINS = [
    "data_governance", "digital_identity", "consent", "privacy", "cybersecurity",
    "digital_public_infrastructure", "interoperability", "institutional_accountability",
    "citizen_rights", "digital_sovereignty",
]

class BaseModel(Model):
    class Meta:
        database = db

class Source(BaseModel):
    source_id = AutoField()
    title = CharField()
    source_type = CharField()
    publisher_or_author = CharField()
    publication_date = DateField(null=True)
    jurisdiction = CharField()
    institution = CharField(null=True)
    url = CharField(null=True, unique=True)
    citation = TextField(null=True)
    language = CharField(default='en')
    access_date = DateField(null=True)
    description = TextField(null=True)
    status = CharField(default=SourceStatus.DISCOVERED.value)
    priority = CharField(default=ResearchPriority.MEDIUM.value)
    research_priority = CharField(default=ResearchPriority.MEDIUM.value)
    jurisdiction_group = CharField(default=JurisdictionGroup.ETHIOPIA.value)
    research_domains = TextField(null=True)
    data_status = CharField(default=DataStatus.REAL.value)
    notes = TextField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

class Evidence(BaseModel):
    evidence_id = AutoField()
    source = ForeignKeyField(Source, backref='evidences')
    title = CharField()
    source_type = CharField()
    publisher_or_author = CharField()
    publication_date = DateField(null=True)
    country_or_jurisdiction = CharField()
    institution = CharField(null=True)
    domain_theme = CharField()
    claim = TextField()
    evidence_summary = TextField()
    source_excerpt = TextField(null=True)
    interpretation = TextField(null=True)
    source_url = CharField(null=True)
    citation = TextField(null=True)
    reliability_level = IntegerField()
    evidence_strength = IntegerField()
    methodology_or_basis = TextField(null=True)
    relevant_policy_or_law = CharField(null=True)
    keywords = TextField(null=True)
    notes = TextField(null=True)
    locator_type = CharField(null=True)
    locator_value = CharField(null=True)
    data_status = CharField(default=DataStatus.REAL.value)
    date_added = DateTimeField(default=datetime.datetime.now)

class GovernanceObservation(BaseModel):
    observation_id = AutoField()
    jurisdiction = CharField()
    system_name = CharField()
    dimension = CharField()
    indicator = CharField()
    observed_evidence = TextField()
    assessment = TextField(null=True)
    confidence = IntegerField(null=True)
    analytical_notes = TextField(null=True)
    data_status = CharField(default=DataStatus.REAL.value)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

class EvidenceObservation(BaseModel):
    observation = ForeignKeyField(GovernanceObservation, backref='evidence_links')
    evidence = ForeignKeyField(Evidence, backref='observation_links')

def initialize_db():
    db.connect(reuse_if_open=True)
    db.create_tables([Source, Evidence, GovernanceObservation, EvidenceObservation])
    db.close()
