from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolName = Literal[
    "search_granules",
    "detect_water_change",
    "detect_disturbance",
    "lake_area_series",
    "precip_percentile",
    "stage_volume",
    "breach_hydrograph",
    "route_flood",
    "exposure_at",
    "precedent",
    "science_lookup",
    "write_status",
    "susceptibility_at",
    "cascade_from",
    "observability_report",
    "met_context",
]

GATED_TOOLS: frozenset[str] = frozenset({"voice_call", "send_sms", "send_whatsapp"})


class SearchGranulesArgs(BaseModel):
    product: str = Field(description="OPERA product short name")
    lon: float
    lat: float
    since_days: int = Field(default=14, description="days to look back from as_of")


class DetectWaterChangeArgs(BaseModel):
    tile: str = Field(description="HLS/Sentinel tile id, e.g. T45RUL")


class DetectDisturbanceArgs(BaseModel):
    tile: str


class LakeAreaSeriesArgs(BaseModel):
    lon: float
    lat: float


class PrecipPercentileArgs(BaseModel):
    target_date: str = Field(description="ISO date, YYYY-MM-DD")


class StageVolumeArgs(BaseModel):
    lon: float
    lat: float
    dam_height_m: float = Field(default=60.0)


class BreachHydrographArgs(BaseModel):
    volume_mm3: float
    duration_minutes: float
    mode: Literal["partial", "full", "progressive"] = "full"


class RouteFloodArgs(BaseModel):
    volume_mm3: float
    duration_minutes: float
    mode: Literal["partial", "full", "progressive"] = "full"


class ExposureAtArgs(BaseModel):
    lon: float
    lat: float
    radius_m: float = Field(default=500.0)


class PrecedentArgs(BaseModel):
    country: str


class ScienceLookupArgs(BaseModel):
    query: str


class SusceptibilityAtArgs(BaseModel):
    node_id: str = Field(description="ICIMOD GL_ID of an inventoried lake")


class CascadeFromArgs(BaseModel):
    node_id: str = Field(description="hazard node id on the corridor drainage network")
    breach_volume_mm3: float = Field(default=1.0)


class ObservabilityReportArgs(BaseModel):
    catchment: str = Field(description="basin name, for example Koshi or Gandaki")


class MetContextArgs(BaseModel):
    basin: str = Field(description="basin name, for example Koshi")
    target_date: str = Field(description="ISO date, YYYY-MM-DD")


class WriteStatusArgs(BaseModel):
    settlement: str
    basin_id: str
    level: Literal["NORMAL", "WATCH"]
    evidence_ref: str


ARGS_MODELS: dict[str, type[BaseModel]] = {
    "search_granules": SearchGranulesArgs,
    "detect_water_change": DetectWaterChangeArgs,
    "detect_disturbance": DetectDisturbanceArgs,
    "lake_area_series": LakeAreaSeriesArgs,
    "precip_percentile": PrecipPercentileArgs,
    "stage_volume": StageVolumeArgs,
    "breach_hydrograph": BreachHydrographArgs,
    "route_flood": RouteFloodArgs,
    "exposure_at": ExposureAtArgs,
    "precedent": PrecedentArgs,
    "science_lookup": ScienceLookupArgs,
    "write_status": WriteStatusArgs,
    "susceptibility_at": SusceptibilityAtArgs,
    "cascade_from": CascadeFromArgs,
    "observability_report": ObservabilityReportArgs,
    "met_context": MetContextArgs,
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "search_granules": (
        "Search NASA CMR for satellite granules published over a point since a lookback window."
    ),
    "detect_water_change": (
        "Read the latest OPERA DSWx-S1 water observation for a tile and classify it against "
        "the self-computed rolling baseline."
    ),
    "detect_disturbance": (
        "Read the latest OPERA DIST-ALERT-HLS disturbance observation for a tile."
    ),
    "lake_area_series": (
        "Build the MNDWI-derived lake area time series at a point, with cloud-obscured "
        "observations flagged."
    ),
    "precip_percentile": (
        "Get the basin-mean rainfall on a date and its percentile within that month, from CHIRPS."
    ),
    "stage_volume": (
        "Compute the stage-volume curve at a blockage point from the DEM, modelling an "
        "explicit dam."
    ),
    "breach_hydrograph": (
        "Compute the peak inflow of a parametric breach hydrograph for a given volume, "
        "duration and shape."
    ),
    "route_flood": (
        "Look up arrival time and peak stage rise per station from the precomputed scenario grid."
    ),
    "exposure_at": "Count population, buildings and bridges within a radius of a point.",
    "precedent": "Look up historical GLOF recurrence for a country from HMAGLOFDB.",
    "science_lookup": "Retrieve grounding text from the science and events knowledge base.",
    "write_status": (
        "Write a settlement's public status. Autonomous only at WATCH or below; anything "
        "higher is refused in code."
    ),
    "susceptibility_at": (
        "Rank one inventoried lake for susceptibility against the other inventoried lakes, "
        "with empirical base rates and the parameters that could not be observed. Returns a "
        "ranking, never a probability of failure and never a date."
    ),
    "cascade_from": (
        "Walk the downstream hazard chain from a node, returning each step with its "
        "confidence, which decays with chain length."
    ),
    "observability_report": (
        "Report how much of a catchment sits below the detection limit, where the answer is "
        "not observable rather than not present."
    ),
    "met_context": (
        "Place a date's rainfall against the CHIRPS climatology and state whether rainfall "
        "plausibly explains an event on that date, with antecedent totals and the layers "
        "this system does not hold."
    ),
}


def _to_function_schema(name: str, model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
        prop.pop("description", None) if "description" not in prop else None
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "parameters": schema,
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _to_function_schema(name, model) for name, model in ARGS_MODELS.items()
]
GATED_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Request {name.replace('_', ' ')}. Requires human approval.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    for name in sorted(GATED_TOOLS)
]
ALL_SCHEMAS: list[dict[str, Any]] = TOOL_SCHEMAS + GATED_SCHEMAS
