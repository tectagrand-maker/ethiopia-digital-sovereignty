import json
from collections import Counter, OrderedDict

from src.evidence.models import (
    Source, Evidence, GovernanceObservation,
    SourceStatus, GOVERNANCE_DIMENSIONS,
)


def research_status_report():
    """Data-quality / research-coverage report (NOT a governance score)."""
    sources = list(Source.select())
    evidence_rows = list(Evidence.select())
    observations = list(GovernanceObservation.select())

    by_group = Counter(s.jurisdiction_group for s in sources)
    by_status = Counter(s.status for s in sources)
    by_domain = Counter()
    for s in sources:
        if s.research_domains:
            for d in str(s.research_domains).split(','):
                d = d.strip()
                if d:
                    by_domain[d] += 1

    evidence_by_status = Counter(e.data_status for e in evidence_rows)
    evidence_by_dimension = Counter()
    for obs in observations:
        evidence_by_dimension[obs.dimension] += 1

    sources_with_evidence = {e.source.source_id for e in evidence_rows}
    sources_without_evidence = [s.source_id for s in sources if s.source_id not in sources_with_evidence]

    evidence_with_observation = {eo.evidence.evidence_id for o in observations for eo in o.evidence_links}
    evidence_without_observation = [e.evidence_id for e in evidence_rows if e.evidence_id not in evidence_with_observation]

    dimensions_with_missing_evidence = [
        d for d in GOVERNANCE_DIMENSIONS
        if d not in evidence_by_dimension
    ]

    return {
        "report_type": "research_status",
        "note": "Coverage counts only. Absence of evidence is not an assessment.",
        "sources": {
            "total": len(sources),
            "by_jurisdiction_group": dict(by_group),
            "by_status": dict(by_status),
            "by_research_domain": dict(by_domain),
            "without_extracted_evidence": sorted(sources_without_evidence),
        },
        "evidence": {
            "total": len(evidence_rows),
            "by_data_status": dict(evidence_by_status),
            "without_governance_observation": sorted(evidence_without_observation),
        },
        "governance": {
            "observations_total": len(observations),
            "evidence_by_dimension": dict(evidence_by_dimension),
            "dimensions_with_missing_evidence": dimensions_with_missing_evidence,
        },
    }


def report_to_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False)
