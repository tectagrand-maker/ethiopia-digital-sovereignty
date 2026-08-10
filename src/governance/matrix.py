"""Evidence coverage matrix and Ethiopia research matrix (Step 6).

These are analytical research-coverage artifacts generated from the database.
They are NOT governance scores. ``missing_evidence`` means exactly that the
current corpus does not yet provide sufficient evidence for a dimension.
"""
from collections import Counter, OrderedDict

from src.evidence.models import (
    Source, Evidence, GovernanceObservation, GOVERNANCE_DIMENSIONS,
)

SUPPORTED_STATUS = "supported"
PARTIAL_STATUS = "partial"
MISSING_STATUS = "missing_evidence"

# Evidence records carry a research-domain theme; observations carry a
# governance dimension. This maps research domains onto governance dimensions
# so the coverage matrix can derive evidence-level coverage. It is an analytical
# convention, documented in docs/evidence-matrix.md.
DOMAIN_TO_DIMENSION = {
    "data_governance": "data_governance",
    "privacy": "data_governance",
    "digital_identity": "digital_identity",
    "consent": "consent_individual_agency",
    "cybersecurity": "security_resilience",
    "digital_public_infrastructure": "state_capacity",
    "interoperability": "interoperability",
    "institutional_accountability": "institutional_accountability",
    "citizen_rights": "citizen_rights_redress",
    "digital_sovereignty": "data_localization",
}

DIMENSION_TO_DOMAIN = {}
for _d, _dim in DOMAIN_TO_DIMENSION.items():
    DIMENSION_TO_DOMAIN.setdefault(_dim, []).append(_d)


def _domain_of(dimension):
    """Primary research domain that maps onto the given governance dimension."""
    domains = DIMENSION_TO_DOMAIN.get(dimension)
    return domains[0] if domains else None


def _real_evidence_rows():
    return list(Evidence.select().where(Evidence.data_status == 'real'))


def _real_observations():
    return list(GovernanceObservation.select().where(
        GovernanceObservation.data_status == 'real'))


def coverage_matrix():
    """Machine-readable coverage matrix across jurisdictions x 12 dimensions.

    Columns: jurisdiction, governance_dimension, source_count,
             evidence_count, observation_count, status.

    Evidence is matched to a dimension either via an observation link
    (authoritative) or, failing that, via the research-domain->dimension map.

    Status is derived from the evidence base:
      - supported:      >=2 real evidence records across >=2 sources
      - partial:        >=1 real evidence record (single source or single record)
      - missing_evidence: no real evidence record
    """
    evidence_rows = _real_evidence_rows()
    observations = _real_observations()

    # Authoritative mapping: (jurisdiction, dimension) -> evidence ids
    # derived from real observation links.
    obs_evidence = {}
    for o in observations:
        key = (o.jurisdiction, o.dimension)
        obs_evidence.setdefault(key, set()).update(
            eo.evidence.evidence_id for eo in o.evidence_links
            if eo.evidence.data_status == 'real'
        )

    # Evidence-level mapping via research domain.
    domain_evidence = {}
    for e in evidence_rows:
        dim = DOMAIN_TO_DIMENSION.get(e.domain_theme)
        if dim:
            domain_evidence.setdefault((e.country_or_jurisdiction, dim), set()).add(e.evidence_id)

    # Merge: observation links take precedence; add domain-mapped evidence.
    cell_evidence = {}
    for key in set(obs_evidence) | set(domain_evidence):
        ids = set(obs_evidence.get(key, set())) | set(domain_evidence.get(key, set()))
        cell_evidence[key] = ids

    obs_by_cell = Counter()
    for o in observations:
        obs_by_cell[(o.jurisdiction, o.dimension)] += 1

    jurisdictions = sorted({j for j, _ in cell_evidence} | {j for j, _ in obs_by_cell})

    rows = []
    for jurisdiction in jurisdictions:
        for dimension in GOVERNANCE_DIMENSIONS:
            key = (jurisdiction, dimension)
            ids = cell_evidence.get(key, set())
            ev_count = len(ids)
            src_count = len({e.source.source_id for e in evidence_rows if e.evidence_id in ids})
            obs_count = obs_by_cell.get(key, 0)
            rows.append({
                "jurisdiction": jurisdiction,
                "governance_dimension": dimension,
                "source_count": src_count,
                "evidence_count": ev_count,
                "observation_count": obs_count,
                "status": _derive_status(ev_count, src_count),
            })
    return rows


def _derive_status(evidence_count, source_count):
    if evidence_count >= 2 and source_count >= 2:
        return SUPPORTED_STATUS
    if evidence_count >= 1:
        return PARTIAL_STATUS
    return MISSING_STATUS


def _jurisdiction_evidence_ids(jurisdiction, dimension):
    """Return evidence IDs for real evidence matching jurisdiction+dimension.

    Matching is performed via observation links where available, falling back
    to the research-domain->dimension map on the evidence record.
    """
    # Preferred: evidence referenced by a real observation for this cell.
    linked = set()
    for o in _real_observations():
        if o.jurisdiction == jurisdiction and o.dimension == dimension:
            for eo in o.evidence_links:
                if eo.evidence.data_status == 'real':
                    linked.add(eo.evidence.evidence_id)
    if linked:
        return sorted(linked)
    # Fallback: evidence-level matching on research domain -> dimension.
    domain = _domain_of(dimension)
    fallback = set()
    for e in _real_evidence_rows():
        if e.country_or_jurisdiction == jurisdiction and e.domain_theme == domain:
            fallback.add(e.evidence_id)
    return sorted(fallback)


def research_matrix(jurisdiction="Ethiopia", include_gaps=True):
    """Ethiopia governance matrix generated from the database.

    For each of the 12 dimensions: evidence_count, source_count,
    observation_count, status, confidence, evidence_ids,
    key_supported_claims, major_gaps.
    """
    observations = _real_observations()
    evidence_rows = _real_evidence_rows()

    dimensions = []
    for dimension in GOVERNANCE_DIMENSIONS:
        obs_rows = [o for o in observations
                    if o.jurisdiction == jurisdiction and o.dimension == dimension]
        evidence_ids = _jurisdiction_evidence_ids(jurisdiction, dimension)

        cell_evidence = [
            e for e in evidence_rows
            if e.evidence_id in evidence_ids
        ]
        source_ids = sorted({e.source.source_id for e in cell_evidence})

        status = _derive_status(len(cell_evidence), len(source_ids))
        confidence = None
        if obs_rows:
            vals = [o.confidence for o in obs_rows if o.confidence]
            confidence = int(round(sum(vals) / len(vals))) if vals else None

        key_supported_claims = [
            e.claim for e in cell_evidence if e.data_status == 'real'
        ][:5]

        dimensions.append({
            "dimension": dimension,
            "evidence_count": len(cell_evidence),
            "source_count": len(source_ids),
            "observation_count": len(obs_rows),
            "status": status,
            "confidence": confidence,
            "evidence_ids": evidence_ids,
            "source_ids": source_ids,
            "key_supported_claims": key_supported_claims,
            "major_gaps": _major_gaps(dimension, cell_evidence, obs_rows),
        })

    return {
        "report_type": "research_matrix",
        "jurisdiction": jurisdiction,
        "note": (
            "Current Evidence Matrix. Coverage counts and evidence-based status "
            "only; missing_evidence is not a negative assessment."
        ),
        "matrix": dimensions,
    }


def _major_gaps(dimension, evidence_rows, obs_rows):
    """Short, structured gap note per dimension (never a negative assessment)."""
    if not evidence_rows:
        return "No real evidence records for this dimension in the current corpus."
    if not obs_rows:
        return "Evidence exists but no governance observation synthesizes it yet."
    return "Coverage is partial; additional source types may be needed."


def matrix_to_csv(matrix_data):
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "dimension", "evidence_count", "source_count", "observation_count",
        "status", "confidence", "evidence_ids", "source_ids",
    ])
    for row in matrix_data["matrix"]:
        writer.writerow([
            row["dimension"],
            row["evidence_count"],
            row["source_count"],
            row["observation_count"],
            row["status"],
            row["confidence"],
            json_dumps(row["evidence_ids"]),
            json_dumps(row["source_ids"]),
        ])
    return buf.getvalue()


def json_dumps(value):
    import json
    return json.dumps(value)
