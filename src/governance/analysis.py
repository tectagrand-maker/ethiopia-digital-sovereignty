import json
import csv
import io
import datetime
from collections import OrderedDict

from src.evidence.models import (
    Evidence, GovernanceObservation, EvidenceObservation,
    DataStatus, GOVERNANCE_DIMENSIONS,
)
from playhouse.shortcuts import model_to_dict

VALID_DIMENSIONS = set(GOVERNANCE_DIMENSIONS)
VALID_CONFIDENCE = {1, 2, 3, 4, 5}
MISSING_STATUS = "missing_evidence"
AVAILABLE_STATUS = "evidence_available"


def create_observation(data: dict, evidence_ids: list):
    """Create a governance observation that references validated evidence IDs.

    Raises ValueError if:
      - the dimension is not one of the 12 controlled dimensions
      - confidence is not an integer 1-5
      - any evidence_id does not exist
      - an observation supplies evidence_ids but none resolve (broken refs)
    """
    dimension = data.get('dimension')
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"Invalid dimension: {dimension!r}. Must be one of: {sorted(VALID_DIMENSIONS)}")

    confidence = data.get('confidence')
    if confidence is not None and int(confidence) not in VALID_CONFIDENCE:
        raise ValueError(f"Invalid confidence: {confidence!r}. Must be an integer 1-5 or null.")

    if evidence_ids is None:
        evidence_ids = []

    obs = GovernanceObservation.create(**data)

    resolved = 0
    for eid in evidence_ids:
        evidence = Evidence.get_or_none(Evidence.evidence_id == eid)
        if not evidence:
            raise ValueError(f"Evidence ID {eid} not found.")
        EvidenceObservation.create(observation=obs, evidence=evidence)
        resolved += 1

    # Refuse observations that claim evidence links but all references are invalid.
    if evidence_ids and resolved == 0:
        obs.delete_instance()
        raise ValueError("Observation references no valid evidence.")

    return obs


def _evidence_metadata(eid):
    evidence = Evidence.get_or_none(Evidence.evidence_id == eid)
    if not evidence:
        return None
    return {
        "evidence_id": eid,
        "title": evidence.title,
        "claim": evidence.claim,
        "source_id": evidence.source.source_id,
        "data_status": evidence.data_status,
        "locator_type": evidence.locator_type,
        "locator_value": evidence.locator_value,
    }


def _observation_payload(obs):
    payload = model_to_dict(obs)
    payload["evidence_ids"] = [eo.evidence.evidence_id for eo in obs.evidence_links]
    payload["evidence"] = [_evidence_metadata(eo.evidence.evidence_id) for eo in obs.evidence_links]
    payload["status"] = AVAILABLE_STATUS
    return payload


def _jurisdiction_dimension_view(jurisdiction, dimension):
    """Return the structured view for one (jurisdiction, dimension) pair.

    If there are no observations for that pair, the view is explicitly
    ``missing_evidence`` with null assessment/confidence -- never an inferred
    negative score.
    """
    obs_rows = list(
        GovernanceObservation.select()
        .where(GovernanceObservation.jurisdiction == jurisdiction,
               GovernanceObservation.dimension == dimension)
    )
    if not obs_rows:
        return {
            "status": MISSING_STATUS,
            "assessment": None,
            "confidence": None,
            "observations": [],
            "evidence_ids": [],
        }
    observations = [_observation_payload(o) for o in obs_rows]
    return {
        "status": AVAILABLE_STATUS,
        "assessment": [o["assessment"] for o in observations if o["assessment"]],
        "confidence": [o["confidence"] for o in observations if o["confidence"]],
        "observations": observations,
        "evidence_ids": sorted({eid for o in observations for eid in o["evidence_ids"]}),
    }


def get_comparative_data(j1, j2, include_all_dimensions=True):
    """Compare two jurisdictions across the 12 governance dimensions.

    Output is deterministic and machine-readable. Dimensions without any
    observation are reported as ``missing_evidence`` -- never as a score.
    """
    result = {
        "comparison": {"jurisdiction_a": j1, "jurisdiction_b": j2},
        "note": "missing_evidence means no observation is recorded; it is NOT an assessment.",
        "dimensions": [],
    }
    dimensions = list(GOVERNANCE_DIMENSIONS)
    if not include_all_dimensions:
        present = set(
            o.dimension for o in GovernanceObservation.select(
                GovernanceObservation.dimension
            ).where(
                (GovernanceObservation.jurisdiction == j1)
                | (GovernanceObservation.jurisdiction == j2)
            )
        )
        dimensions = [d for d in dimensions if d in present]

    for dim in dimensions:
        result["dimensions"].append({
            "dimension": dim,
            j1: _jurisdiction_dimension_view(j1, dim),
            j2: _jurisdiction_dimension_view(j2, dim),
        })
    return result


def comparison_to_json(data):
    def _default(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=_default)


def comparison_to_csv(data):
    """Flatten comparison output to CSV rows (one per jurisdiction/dimension)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "dimension", "jurisdiction", "status", "assessment", "confidence",
        "evidence_ids", "observation_count",
    ])
    for dim in data["dimensions"]:
        for jurisdiction in (data["comparison"]["jurisdiction_a"], data["comparison"]["jurisdiction_b"]):
            view = dim[jurisdiction]
            writer.writerow([
                dim["dimension"],
                jurisdiction,
                view["status"],
                json.dumps(view["assessment"]),
                json.dumps(view["confidence"]),
                json.dumps(view["evidence_ids"]),
                len(view["observations"]),
            ])
    return buf.getvalue()
