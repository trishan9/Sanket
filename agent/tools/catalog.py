from __future__ import annotations

from datetime import date
from typing import Any

from agent.rag.retrieve import retrieve
from agent.tools.context import ToolContext
from agent.tools.risk_tools import RISK_DISPATCH
from analysis.eo.baselines import load_baseline
from analysis.eo.changedetect import classify
from analysis.eo.dist import disturbance_area_km2
from analysis.eo.dist import observations_for_tile as dist_observations
from analysis.eo.dswx import observations_for_tile as dswx_observations
from analysis.eo.dswx import water_area_km2
from analysis.eo.lake_series import build_series
from analysis.eo.precip import percentile_for_date
from analysis.exposure.cells import exposure_at as exposure_at_geometry
from analysis.hydro.breach import breach_hydrograph as compute_breach
from analysis.hydro.breach import peak_inflow
from analysis.hydro.scenarios import ScenarioKey, load_scenario
from analysis.hydro.stage_volume import stage_volume as compute_stage_volume
from core.board import write_status as write_status_action
from core.connectors.opera import search as cmr_search
from core.errors import DetectionError, RegistryError
from core.provenance import Evidence, Provenance, Uncertainty

DEFAULT_TILE = "T45RUL"
DEFAULT_BBOX = (85.10, 27.80, 85.45, 28.55)




def search_granules(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    results = cmr_search(args["product"], DEFAULT_BBOX)
    return Evidence(
        value={"count": len(results), "product": args["product"]},
        provenance=Provenance(
            source="NASA CMR",
            method="collection search",
            as_of_filter=ctx.as_of,
        ),
        claim_type="observation",
    )


def detect_water_change(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    tile = args["tile"]
    observations = [o for o in dswx_observations(tile) if o.acquired.date() <= ctx.as_of]
    if not observations:
        raise DetectionError(f"no DSWx-S1 observations for {tile} as of {ctx.as_of}")
    latest = observations[-1]
    observed = water_area_km2(latest)
    baseline = load_baseline("OPERA_L3_DSWX-S1_V1", tile, "water_area_km2", ctx.store)
    signal = classify(observed, baseline) if baseline else None
    return Evidence(
        value={
            "tile": tile,
            "water_area_km2": round(observed, 4),
            "z": round(signal.z, 3) if signal else None,
            "classification": signal.classification if signal else "no_baseline",
            "acquired": latest.acquired.isoformat(),
        },
        provenance=Provenance(
            source="OPERA DSWx-S1",
            method="WTR band, open+partial water classes",
            as_of_filter=ctx.as_of,
            acquired=latest.acquired,
            independence_group="opera_radar_water",
        ),
        claim_type="observation",
    )


def detect_disturbance(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    tile = args["tile"]
    observations = [o for o in dist_observations(tile) if o.acquired.date() <= ctx.as_of]
    if not observations:
        raise DetectionError(f"no DIST-ALERT observations for {tile} as of {ctx.as_of}")
    latest = observations[-1]
    return Evidence(
        value={
            "tile": tile,
            "confirmed_disturbance_km2": round(disturbance_area_km2(latest), 4),
            "acquired": latest.acquired.isoformat(),
        },
        provenance=Provenance(
            source="OPERA DIST-ALERT-HLS v1",
            method="VEG-DIST-STATUS confirmed classes",
            as_of_filter=ctx.as_of,
            acquired=latest.acquired,
            independence_group="opera_optical_disturbance",
        ),
        claim_type="observation",
    )


def lake_area_series(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    series = [o for o in build_series(args["lon"], args["lat"]) if o.acquired.date() <= ctx.as_of]
    clear = [o for o in series if not o.obscured]
    return Evidence(
        value={
            "n_observations": len(series),
            "n_clear": len(clear),
            "n_obscured": len(series) - len(clear),
            "latest_clear_area_km2": round(clear[-1].area_km2, 4) if clear else None,
            "latest_clear_date": clear[-1].acquired.isoformat() if clear else None,
        },
        provenance=Provenance(
            source="Sentinel-2 L2A / MNDWI",
            method="MNDWI + bounded Otsu threshold",
            as_of_filter=ctx.as_of,
            independence_group="sanket_optical",
            uncertainty=Uncertainty(note="detection floor ~0.003 km2"),
        ),
        claim_type="observation",
    )


def precip_percentile(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    target = date.fromisoformat(args["target_date"])
    if target > ctx.as_of:
        raise DetectionError(f"{target} is after as_of={ctx.as_of}; cannot look into the future")
    obs = percentile_for_date(target)
    return Evidence(
        value={
            "date": obs.target_date.isoformat(),
            "basin_mean_mm": round(obs.basin_mean_mm, 2),
            "month_mean_mm": round(obs.month_mean_mm, 2),
            "percentile_within_month": round(obs.percentile_within_month, 1),
        },
        provenance=Provenance(
            source=obs.source,
            method="basin-mean daily rainfall vs same-month distribution",
            as_of_filter=ctx.as_of,
            independence_group="chirps_precipitation",
        ),
        claim_type="observation",
    )


def stage_volume(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    return compute_stage_volume(
        args["lon"],
        args["lat"],
        as_of=ctx.as_of,
        dam_height_m=args.get("dam_height_m", 60.0),
    )


def breach_hydrograph(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    volume = args["volume_mm3"] * 1e6
    duration = args["duration_minutes"] * 60
    hydrograph = compute_breach(volume, duration, args.get("mode", "full"))
    peak = peak_inflow(hydrograph, duration)
    return Evidence(
        value={
            "volume_mm3": args["volume_mm3"],
            "duration_minutes": args["duration_minutes"],
            "mode": args.get("mode", "full"),
            "peak_inflow_m3s": round(peak, 1),
        },
        provenance=Provenance(
            source="derived",
            method="parametric gamma/triangular breach hydrograph",
            as_of_filter=ctx.as_of,
        ),
        claim_type="model_output",
    )


def route_flood(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    key = ScenarioKey(args["volume_mm3"], args["duration_minutes"] * 60, args.get("mode", "full"))
    try:
        data = load_scenario(key.slug)
    except FileNotFoundError as exc:
        raise RegistryError(f"no precomputed scenario for {key.slug}") from exc
    import numpy as np

    arrival = data["arrival_time_s"]
    valid = arrival[np.isfinite(arrival)]
    return Evidence(
        value={
            "scenario": key.slug,
            "settlements_with_arrival": int(len(valid)),
            "fastest_arrival_minutes": round(float(valid.min()) / 60, 1) if len(valid) else None,
            "max_peak_rise_m": round(float(np.nanmax(data["peak_rise_m"])), 2),
        },
        provenance=Provenance(
            source="precomputed scenario grid",
            method="1D Saint-Venant router, Rusanov flux",
            as_of_filter=ctx.as_of,
            caveats=(
                "the DEM predates the event; post-event routing is wrong in ways we cannot "
                "correct without new survey",
                "a water-only shallow-water solver, not a two-phase debris flow",
            ),
        ),
        claim_type="scenario",
    )


def exposure_at(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    from pyproj import Transformer
    from shapely.geometry import Point

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    x, y = transformer.transform(args["lon"], args["lat"])
    geometry = Point(x, y).buffer(args.get("radius_m", 500.0))
    exposure = exposure_at_geometry(geometry)
    return Evidence(
        value={
            "population": round(exposure.population),
            "buildings": exposure.buildings,
            "bridges": exposure.bridges,
            "settlements": list(exposure.settlements),
            "radius_m": args.get("radius_m", 500.0),
        },
        provenance=Provenance(
            source="WorldPop 2020 + OSM/HOT",
            method="raster mask sum + vector intersection",
            as_of_filter=ctx.as_of,
            independence_group="worldpop_population",
            caveats=("population is modelled usual residence, not a count",),
        ),
        claim_type="model_output",
    )


def precedent(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    import pandas as pd

    from core.config import paths

    df = pd.read_csv(
        paths.bronze / "hmaglofdb" / "HMAGLOFDB.csv", low_memory=False, encoding="latin-1"
    )
    country = args["country"]
    matches = df[df["Country"] == country]
    return Evidence(
        value={
            "country": country,
            "historical_glof_count": int(len(matches)),
            "lake_types": matches["Lake_type"].value_counts().to_dict(),
        },
        provenance=Provenance(
            source="HMAGLOFDB",
            method="country-level event count, 1833-2022",
            as_of_filter=ctx.as_of,
            independence_group="hmaglofdb_record",
            caveats=("documentary record, not exhaustive",),
        ),
        claim_type="observation",
    )


def science_lookup(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    result = retrieve("science", args["query"], as_of=ctx.as_of, k=4)
    return Evidence(
        value={
            "query": args["query"],
            "results": [
                {
                    "text": chunk.text,
                    "source_org": chunk.source_org,
                    "url": chunk.url,
                    "published_at": chunk.published_at,
                }
                for chunk in result.chunks
            ],
            "n_dropped_injection": len(result.dropped),
            "n_rejected_post_cutoff": result.rejected_post_cutoff,
        },
        provenance=Provenance(
            source="ChromaDB science collection",
            method="multilingual sentence embedding, cosine similarity",
            as_of_filter=ctx.as_of,
            caveats=("retrieved text grounds the model; it is not itself verified evidence",),
        ),
        claim_type="observation",
    )


def write_status(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    result = write_status_action(
        args["settlement"],
        args["basin_id"],
        args["level"],
        run_id=ctx.run_id,
        store=ctx.store,
    )
    return Evidence(
        value=result,
        provenance=Provenance(
            source="SANKET Actor",
            method="autonomous board write",
            as_of_filter=ctx.as_of,
        ),
        claim_type="observation",
    )


DISPATCH = {
    "search_granules": search_granules,
    "detect_water_change": detect_water_change,
    "detect_disturbance": detect_disturbance,
    "lake_area_series": lake_area_series,
    "precip_percentile": precip_percentile,
    "stage_volume": stage_volume,
    "breach_hydrograph": breach_hydrograph,
    "route_flood": route_flood,
    "exposure_at": exposure_at,
    "precedent": precedent,
    "science_lookup": science_lookup,
    "write_status": write_status,
    **RISK_DISPATCH,
}
