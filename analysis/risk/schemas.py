from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal[
    "moraine_lake",
    "ice_dammed_lake",
    "supraglacial_lake",
    "bedrock_lake",
    "landslide_dam",
    "debris_dam",
    "barrier_lake",
    "reservoir",
    "confluence",
    "settlement",
]

DamType = Literal["moraine", "ice", "bedrock", "landslide_debris", "unknown"]

SusceptibilityBand = Literal["very_high", "high", "moderate", "low", "not_assessable"]

ObservabilityState = Literal["observable", "below_detection_limit", "obscured", "no_coverage"]

CONFIDENCE_DECAY_PER_STEP = 0.62


class ParameterValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    group: Literal["dam", "lake", "trigger", "conditioning", "downstream"]
    value: float | None
    unit: str
    source: str
    observable: bool = True
    note: str = ""


class BaseRate(BaseModel):
    model_config = ConfigDict(frozen=True)

    stratum: str
    events: int
    population: int
    rate_per_lake: float
    ci_low: float
    ci_high: float
    sample_size: int
    record_period: str
    caveat: str

    def rendered(self) -> str:
        return (
            f"{self.stratum}: {self.events} recorded events across {self.population} "
            f"inventoried lakes, {self.rate_per_lake:.4f} events per lake "
            f"(95% CI {self.ci_low:.4f}-{self.ci_high:.4f}, n={self.sample_size}, "
            f"{self.record_period})"
        )


class SusceptibilityScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    rank_score: float = Field(ge=0.0, le=1.0)
    band: SusceptibilityBand
    parameters: tuple[ParameterValue, ...]
    base_rates: tuple[BaseRate, ...]
    unobservable_parameters: tuple[str, ...]
    frameworks: tuple[str, ...]
    caveats: tuple[str, ...]

    def rendered(self) -> str:
        return (
            f"{self.node_id}: susceptibility band {self.band}, relative rank score "
            f"{self.rank_score:.3f}. This is a ranking against other inventoried lakes, "
            "not a probability of failure and not a forecast of when any lake may fail."
        )


class HazardNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    node_type: NodeType
    location: tuple[float, float]
    area_km2: float | None = None
    elevation_m: float | None = None
    chainage_m: float | None = None
    dam_type: DamType = "unknown"
    label: str = ""
    downstream: tuple[str, ...] = ()


class CascadeStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    order: int
    node_id: str
    node_type: NodeType
    mechanism: str
    confidence: float
    volume_mm3: float | None = None
    note: str = ""


class CascadeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    origin_node_id: str
    steps: tuple[CascadeStep, ...]
    terminal_confidence: float
    decay_per_step: float
    caveats: tuple[str, ...]

    def rendered(self) -> str:
        chain = " -> ".join(f"{s.node_id}({s.confidence:.2f})" for s in self.steps)
        return (
            f"cascade from {self.origin_node_id}: {chain}. Confidence decays "
            f"{self.decay_per_step:.2f} per step; this is a scenario chain, not a "
            "statement that any step will occur."
        )


class ObservabilityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    catchment: str
    inventoried_lakes: int
    below_detection_limit: int
    below_attention_threshold: int
    detection_limit_km2: float
    attention_threshold_km2: float
    smallest_inventoried_km2: float
    states: dict[str, ObservabilityState]
    caveats: tuple[str, ...]

    def rendered(self) -> str:
        return (
            f"{self.catchment}: {self.inventoried_lakes} inventoried water bodies. "
            f"{self.below_detection_limit} sit at or below the "
            f"{self.detection_limit_km2} km2 detection limit and are reported as not "
            "observable, which is not the same as not present."
        )
