from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from core.provenance import Evidence
from core.state import State
from core.state import state as default_state

Level = Literal["NORMAL", "WATCH", "ALERT", "INSUFFICIENT"]

LEVEL_ORDER: dict[Level, int] = {"NORMAL": 0, "INSUFFICIENT": 1, "WATCH": 2, "ALERT": 3}

AUTONOMOUS_CEILING: Level = "WATCH"


def requires_approval(level: Level) -> bool:
    return LEVEL_ORDER[level] > LEVEL_ORDER[AUTONOMOUS_CEILING]


def write_status(
    settlement: str,
    basin_id: str,
    level: Level,
    *,
    evidence: Evidence | None = None,
    lead_time_minutes: float | None = None,
    confidence: str | None = None,
    run_id: str | None = None,
    store: State | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if requires_approval(level):
        raise PermissionError(
            f"level {level} exceeds the autonomous ceiling {AUTONOMOUS_CEILING}; "
            "a named district officer must approve"
        )
    target = store or default_state
    payload = _evidence_payload(evidence)
    if extra:
        payload.update(extra)
    target.write_status(
        settlement,
        basin_id,
        level,
        lead_time_minutes=lead_time_minutes,
        confidence=confidence,
        evidence=payload,
        run_id=run_id,
    )
    return {
        "settlement": settlement,
        "basin_id": basin_id,
        "level": level,
        "lead_time_minutes": lead_time_minutes,
        "confidence": confidence,
        "written_at": datetime.now(UTC).isoformat(),
    }


def _evidence_payload(evidence: Evidence | None) -> dict[str, Any]:
    if evidence is None:
        return {}
    return {
        "ref": evidence.ref,
        "claim_type": evidence.claim_type,
        "render_style": evidence.render_style,
        "source": evidence.provenance.source,
        "method": evidence.provenance.method,
        "dataset_vintage": evidence.provenance.dataset_vintage,
        "caveats": list(evidence.provenance.caveats),
        "value": evidence.value,
    }
