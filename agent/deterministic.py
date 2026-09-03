from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent.ledger import Ledger
from agent.tools.catalog import (
    ToolContext,
    breach_hydrograph,
    detect_disturbance,
    detect_water_change,
    exposure_at,
    lake_area_series,
    precip_percentile,
    route_flood,
    stage_volume,
)
from agent.trace import Trace
from core.config import settings
from core.corridor import Corridor
from core.errors import SanketError
from core.provenance import Evidence

DETERMINISTIC_TILE = "T45RUL"
FIXED_DURATION_MINUTES = 30.0
FIXED_MODE = "full"


def _nearest_grid_volume(volume_mm3: float) -> float:
    return min(settings.scenario_volumes_mm3, key=lambda v: abs(v - volume_mm3))


def _try(
    trace: Trace,
    name: str,
    fn: Callable[[dict[str, Any], ToolContext], Evidence],
    args: dict[str, Any],
    ctx: ToolContext,
    ledger: Ledger,
) -> Evidence | None:
    try:
        evidence = fn(args, ctx)
    except SanketError as exc:
        trace.tool(name, args, f"deterministic mode error: {type(exc).__name__}: {exc}")
        return None
    ledger.add(evidence)
    trace.tool(name, args, f"deterministic ref={evidence.ref} claim_type={evidence.claim_type}")
    return evidence


def _gather_observations(
    feature_id: str, lon: float, lat: float, ctx: ToolContext, ledger: Ledger, trace: Trace
) -> tuple[Evidence | None, Evidence | None]:
    lake = _try(trace, "lake_area_series", lake_area_series, {"lon": lon, "lat": lat}, ctx, ledger)
    water = _try(
        trace, "detect_water_change", detect_water_change, {"tile": DETERMINISTIC_TILE}, ctx, ledger
    )
    if water is None:
        water = _try(
            trace,
            "detect_disturbance",
            detect_disturbance,
            {"tile": DETERMINISTIC_TILE},
            ctx,
            ledger,
        )
    precip = _try(
        trace,
        "precip_percentile",
        precip_percentile,
        {"target_date": ctx.as_of.isoformat()},
        ctx,
        ledger,
    )
    observation_refs = [e.ref for e in (lake, water, precip) if e is not None]
    if observation_refs:
        ledger.propose_claim(
            f"deterministic-mode observations for {feature_id}", "observation", observation_refs
        )
    stage = _try(trace, "stage_volume", stage_volume, {"lon": lon, "lat": lat}, ctx, ledger)
    if stage is not None:
        ledger.propose_claim(
            f"deterministic-mode stage-volume for {feature_id}", "model_output", [stage.ref]
        )
    return stage, water


def _gather_hydraulic_chain(
    feature_id: str, stage: Evidence, ctx: ToolContext, ledger: Ledger, trace: Trace
) -> None:
    volume_mm3 = _nearest_grid_volume(float(stage.value.get("max_volume_Mm3", 0.0)))
    args = {
        "volume_mm3": volume_mm3,
        "duration_minutes": FIXED_DURATION_MINUTES,
        "mode": FIXED_MODE,
    }
    breach = _try(trace, "breach_hydrograph", breach_hydrograph, args, ctx, ledger)
    if breach is None:
        return
    ledger.propose_claim(
        f"deterministic-mode breach hydrograph for {feature_id} at nearest grid volume "
        f"{volume_mm3} Mm3",
        "model_output",
        [breach.ref],
    )
    route = _try(trace, "route_flood", route_flood, args, ctx, ledger)
    if route is None:
        return
    ledger.propose_claim(
        f"deterministic-mode scenario routing for {feature_id}", "scenario", [breach.ref, route.ref]
    )


def _conclude(ledger: Ledger, trace: Trace) -> None:
    if ledger.claims:
        ledger.conclude(
            "deterministic mode: fixed tool sequence completed with no LLM provider reachable "
            "for adaptive investigation, contradiction checking, or context generation"
        )
        trace.done("deterministic investigation concluded")
    else:
        ledger.escalate(
            None, "deterministic mode could not gather any evidence; escalating to a human"
        )
        trace.done("deterministic investigation escalated: no evidence gathered")


def run_deterministic_investigation(
    corridor: Corridor,
    feature_id: str,
    ctx: ToolContext,
    ledger: Ledger,
    trace: Trace,
) -> None:
    feature = corridor.feature(feature_id)
    lon, lat = feature.location
    trace.degraded(
        "investigator: no LLM provider reachable - degraded to deterministic mode, running "
        "a fixed tool sequence instead of adaptive tool selection"
    )
    stage, _water = _gather_observations(feature_id, lon, lat, ctx, ledger, trace)
    if stage is not None:
        _gather_hydraulic_chain(feature_id, stage, ctx, ledger, trace)
    exposure = _try(trace, "exposure_at", exposure_at, {"lon": lon, "lat": lat}, ctx, ledger)
    if exposure is not None:
        ledger.propose_claim(
            f"deterministic-mode exposure at {feature_id}", "model_output", [exposure.ref]
        )
    _conclude(ledger, trace)
