import json
from collections import Counter, OrderedDict

from src.evidence.models import (
    Source, Evidence, GovernanceObservation, EvidenceRelation,
    SourceStatus, GOVERNANCE_DIMENSIONS,
)


def research_status_report():
    """Data-quality / research-coverage report (NOT a governance score)."""
    sources = list(Source.select())
    evidence_rows = list(Evidence.select())
    observations = list(GovernanceObservation.select())
    relations = list(EvidenceRelation.select())

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

    # Phase 15: locator completeness (real evidence only).
    real_evidence = [e for e in evidence_rows if e.data_status == 'real']
    with_locator = [e for e in real_evidence if e.locator_type and e.locator_value]
    missing_locator = [e.evidence_id for e in real_evidence
                       if not (e.locator_type and e.locator_value)]

    # Phase 15: single- vs multi-source observations (real only).
    single_source = []
    multi_source = []
    weak_support = []
    for o in observations:
        if o.data_status != 'real':
            continue
        links = list(o.evidence_links)
        src_ids = {eo.evidence.source.source_id for eo in links}
        if len(src_ids) >= 2:
            multi_source.append(o.observation_id)
        elif len(links) >= 1:
            single_source.append(o.observation_id)
            if (o.confidence or 0) <= 2:
                weak_support.append(o.observation_id)

    # Phase 15: evidence per source.
    evidence_per_source = Counter()
    for e in evidence_rows:
        if e.data_status == 'real':
            evidence_per_source[e.source.source_id] += 1

    # Phase 15: unresolved contradictions (relations marked contradicts).
    contradictions = []
    for rel in relations:
        if rel.relation_type == 'contradicts':
            contradictions.append({
                "evidence_a": rel.evidence_a.evidence_id,
                "evidence_b": rel.evidence_b.evidence_id,
                "notes": rel.notes,
            })

    return {
        "report_type": "research_status",
        "note": "Coverage counts only. Absence of evidence is not an assessment.",
        "sources": {
            "total": len(sources),
            "by_jurisdiction_group": dict(by_group),
            "by_status": dict(by_status),
            "by_research_domain": dict(by_domain),
            "coverage": _source_coverage(sources, evidence_rows),
            "without_extracted_evidence": sorted(sources_without_evidence),
        },
        "evidence": {
            "total": len(evidence_rows),
            "by_data_status": dict(evidence_by_status),
            "real_total": len(real_evidence),
            "evidence_per_source": dict(sorted(evidence_per_source.items())),
            "evidence_per_dimension": dict(evidence_by_dimension),
            "with_locators": len(with_locator),
            "missing_locators": sorted(missing_locator),
            "without_governance_observation": sorted(evidence_without_observation),
        },
        "governance": {
            "observations_total": len(observations),
            "evidence_by_dimension": dict(evidence_by_dimension),
            "dimensions_with_missing_evidence": dimensions_with_missing_evidence,
            "single_source_observations": sorted(single_source),
            "multi_source_observations": sorted(multi_source),
            "weak_support_observations": sorted(weak_support),
        },
        "gaps": {
            "dimensions_with_missing_evidence": dimensions_with_missing_evidence,
            "sources_without_evidence": sorted(sources_without_evidence),
            "unresolved_contradictions": contradictions,
        },
    }


def _source_coverage(sources, evidence_rows):
    """Summarise source lifecycle coverage counts."""
    total = len(sources)
    real = [s for s in sources if s.data_status == 'real']
    accessed = sum(1 for s in real if s.status in ('accessed', 'extracted', 'verified'))
    extracted = sum(1 for s in real if s.status in ('extracted', 'verified'))
    verified = sum(1 for s in real if s.status == 'verified')
    queued = sum(1 for s in real if s.status == 'queued')
    discovered = sum(1 for s in real if s.status == 'discovered')
    with_evidence = sum(1 for s in real if s.source_id in {e.source.source_id for e in evidence_rows})
    return {
        "real_total": len(real),
        "accessed": accessed,
        "extracted": extracted,
        "verified": verified,
        "queued": queued,
        "discovered": discovered,
        "sources_with_evidence": with_evidence,
    }


def report_to_json(report):
    return json.dumps(report, indent=2, ensure_ascii=False)
