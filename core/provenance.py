from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.errors import ProvenanceError

ClaimType = Literal[
    "observation", "correlation", "model_output", "scenario", "hypothesis", "recommendation"
]

CLAIM_TYPES: tuple[ClaimType, ...] = (
    "observation",
    "correlation",
    "model_output",
    "scenario",
    "hypothesis",
    "recommendation",
)

RenderStyle = Literal["measured", "derived", "projected", "tentative", "advisory"]

RENDER_STYLE: dict[ClaimType, RenderStyle] = {
    "observation": "measured",
    "correlation": "derived",
    "model_output": "derived",
    "scenario": "projected",
    "hypothesis": "tentative",
    "recommendation": "advisory",
}

PERMITTED_EVIDENCE: dict[ClaimType, frozenset[ClaimType]] = {
    "observation": frozenset({"observation"}),
    "correlation": frozenset({"observation", "correlation"}),
    "model_output": frozenset({"observation", "correlation", "model_output"}),
    "scenario": frozenset({"observation", "correlation", "model_output", "scenario"}),
    "hypothesis": frozenset(CLAIM_TYPES),
    "recommendation": frozenset(CLAIM_TYPES),
}

REQUIRED_EVIDENCE: dict[ClaimType, frozenset[ClaimType]] = {
    "observation": frozenset({"observation"}),
    "correlation": frozenset({"observation", "correlation"}),
    "model_output": frozenset({"model_output"}),
    "scenario": frozenset({"model_output", "scenario"}),
    "hypothesis": frozenset(CLAIM_TYPES),
    "recommendation": frozenset(CLAIM_TYPES),
}


class Uncertainty(BaseModel):
    model_config = ConfigDict(extra="allow")

    pixel_area_m2: float | None = None
    layover_shadow_frac: float | None = None
    cloud_fraction: float | None = None
    relative_error: float | None = None
    note: str | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    method: str
    as_of_filter: date
    granule_ids: tuple[str, ...] = ()
    acquired: datetime | None = None
    published: datetime | None = None
    license: str | None = None
    independence_group: str | None = None
    dataset_vintage: str | None = None
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    caveats: tuple[str, ...] = ()

    @field_validator("source", "method")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("provenance source and method must be non-empty")
        return value

    def age_hours(self, at: datetime) -> float | None:
        if self.acquired is None:
            return None
        return (at - self.acquired).total_seconds() / 3600.0


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: dict[str, Any]
    provenance: Provenance
    claim_type: ClaimType

    @property
    def render_style(self) -> RenderStyle:
        return RENDER_STYLE[self.claim_type]

    @property
    def ref(self) -> str:
        payload = json.dumps(
            {
                "source": self.provenance.source,
                "method": self.provenance.method,
                "granules": list(self.provenance.granule_ids),
                "value": self.value,
            },
            sort_keys=True,
            default=str,
        )
        return "ev_" + hashlib.sha256(payload.encode()).hexdigest()[:12]


class EvidenceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    source: str
    independence_group: str | None = None
    claim_type: ClaimType


def licenses_claim(evidence_types: frozenset[ClaimType], claim_type: ClaimType) -> bool:
    if not evidence_types:
        return False
    if not evidence_types <= PERMITTED_EVIDENCE[claim_type]:
        return False
    return bool(evidence_types & REQUIRED_EVIDENCE[claim_type])


def independence_count(refs: tuple[EvidenceRef, ...]) -> int:
    groups: set[str] = set()
    ungrouped = 0
    for ref in refs:
        if ref.independence_group is None:
            ungrouped += 1
        else:
            groups.add(ref.independence_group)
    return len(groups) + ungrouped


def assert_render_separation(a: ClaimType, b: ClaimType) -> None:
    if a != b and RENDER_STYLE[a] == RENDER_STYLE[b] and {a, b} == {"observation", "scenario"}:
        raise ProvenanceError("scenario must never render in the same style as observation")
