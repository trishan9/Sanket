from __future__ import annotations

import json
from typing import Any

from flask import jsonify, request

from actions.escalation import STAGE_ORDER, EscalationInput, Stage, decide, ladder
from analysis.risk.cascade_graph import NODE_TO_DAM, build_graph
from analysis.risk.prediction import INDICATORS, estimate_hazard
from analysis.risk.rootcause import attribute
from core.config import paths
from core.corridor import Corridor, load_all_corridors

FORMED_NODE_TYPES = frozenset({"barrier_lake", "landslide_dam", "debris_dam"})


def _corridor() -> Corridor:
    return load_all_corridors()["bhotekoshi"]


def _observations_from_args() -> dict[str, bool | None]:
    observations: dict[str, bool | None] = {}
    for indicator in INDICATORS:
        raw = request.args.get(indicator.key)
        if raw is None or raw == "unknown":
            continue
        observations[indicator.key] = raw.lower() in {"1", "true", "yes", "present"}
    return observations


def indicators() -> Any:
    return jsonify(
        {
            "indicators": [
                {
                    "key": item.key,
                    "label": item.label,
                    "likelihood_ratio_present": item.likelihood_ratio_present,
                    "likelihood_ratio_absent": item.likelihood_ratio_absent,
                    "citation": item.citation,
                    "rationale": item.rationale,
                }
                for item in INDICATORS
            ]
        }
    )


def _hazard_payload(estimate: Any, node_type: str) -> dict[str, Any]:
    return {
        "node_id": estimate.node_id,
        "node_type": node_type,
        "dam_type": estimate.dam_type,
        "window_days": estimate.window_days,
        "prior_probability": estimate.prior_probability,
        "posterior_probability": estimate.posterior_probability,
        "credible_interval": list(estimate.credible_interval),
        "lift": estimate.lift,
        "dominant_indicator": estimate.dominant_indicator,
        "unobserved": list(estimate.unobserved),
        "method": estimate.method,
        "steps": list(estimate.steps),
        "caveats": list(estimate.caveats),
        "summary": estimate.rendered(),
        "readings": [
            {
                "key": reading.key,
                "state": reading.state,
                "likelihood_ratio": reading.likelihood_ratio,
                "log_contribution": reading.log_contribution,
                "detail": reading.detail,
            }
            for reading in estimate.readings
        ],
    }


def predict(node_id: str) -> Any:
    nodes = build_graph(_corridor())
    node = nodes.get(node_id)
    node_type = node.node_type if node else "barrier_lake"
    estimate = estimate_hazard(
        node_id,
        NODE_TO_DAM.get(node_type, "unknown"),
        _observations_from_args(),
        int(request.args.get("window_days", 7)),
        already_formed=node_type in FORMED_NODE_TYPES,
        days_since_formation=float(request.args.get("days_since_formation", 1.0)),
    )
    return jsonify(_hazard_payload(estimate, node_type))


def _per_node_observations(nodes: dict[str, Any]) -> dict[str, dict[str, bool | None]]:
    shared = _observations_from_args()
    by_node: dict[str, dict[str, bool | None]] = {}
    for node_id, node in nodes.items():
        if node.node_type == "settlement":
            continue
        scoped: dict[str, bool | None] = {}
        for indicator in INDICATORS:
            raw = request.args.get(f"{node_id}.{indicator.key}")
            if raw is None or raw == "unknown":
                continue
            scoped[indicator.key] = raw.lower() in {"1", "true", "yes", "present"}
        by_node[node_id] = scoped or dict(shared)
    return by_node


def rootcause(settlement: str) -> Any:
    corridor = _corridor()
    nodes = build_graph(corridor)
    by_node = _per_node_observations(nodes)
    result = attribute(corridor, settlement, by_node, int(request.args.get("window_days", 7)))
    return jsonify(
        {
            "observed_at": result.observed_at,
            "window_days": result.window_days,
            "summary": result.rendered(),
            "indistinguishable": list(result.indistinguishable),
            "candidates": [
                {
                    "node_id": item.node_id,
                    "node_type": item.node_type,
                    "steps_downstream": item.steps_downstream,
                    "prior_probability": item.prior_probability,
                    "posterior_probability": item.posterior_probability,
                    "share": item.share,
                    "supporting": list(item.supporting),
                    "contradicting": list(item.contradicting),
                    "unobserved": list(item.unobserved),
                    "summary": item.rendered(),
                }
                for item in result.candidates
            ],
            "caveats": list(result.caveats),
        }
    )


def escalation_ladder() -> Any:
    return jsonify({"stages": list(ladder())})


def _previous_stage() -> Stage | None:
    raw = request.args.get("previous")
    return raw if raw in STAGE_ORDER else None


def escalation_simulate() -> Any:
    signal = EscalationInput(
        indicators_present=int(request.args.get("indicators", 0)),
        hazard_probability=float(request.args.get("probability", 0.0)),
        verifier_passed=request.args.get("verifier_passed", "false").lower() == "true",
        verifier_vetoed=request.args.get("verifier_vetoed", "false").lower() == "true",
    )
    result = decide(signal, _previous_stage())
    return jsonify(
        {
            "stage": result.stage,
            "level": result.level,
            "previous_stage": result.previous_stage,
            "autonomous": result.autonomous,
            "escalated": result.escalated,
            "changed": result.changed,
            "headline": result.headline,
            "headline_nepali": result.headline_nepali,
            "meaning": result.meaning,
            "reason": result.reason,
            "at": result.at.isoformat(),
            "summary": result.rendered(),
        }
    )


def _settlement_features(corridor: Corridor) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(station.location)},
                "properties": {
                    "name": station.name,
                    "district": station.district,
                    "kind": "settlement",
                },
            }
            for station in corridor.downstream_reach
        ],
    }


def _watched_features(corridor: Corridor) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(feature.location)},
                "properties": {
                    "name": feature.id,
                    "kind": feature.type,
                    "first_seen": feature.first_seen.isoformat() if feature.first_seen else None,
                },
            }
            for feature in corridor.watched_features
        ],
    }


def map_layers() -> Any:
    corridor = _corridor()
    settlements = _settlement_features(corridor)
    features = _watched_features(corridor)
    lakes_path = paths.dist / "lake_polygons.geojson"
    lakes = (
        json.loads(lakes_path.read_text(encoding="utf-8"))
        if lakes_path.exists()
        else {"type": "FeatureCollection", "features": []}
    )
    return jsonify(
        {
            "bbox": list(corridor.bbox),
            "settlements": settlements,
            "watched_features": features,
            "lakes": lakes,
            "flood_path": _flood_geojson(),
            "corridor_cells": _corridor_cells(),
            "dem_vintage": corridor.dem_vintage.isoformat(),
        }
    )


def _corridor_cells() -> dict[str, Any]:
    from analysis.exposure.corridor_cells import cells_geojson

    return cells_geojson()


def _flood_geojson() -> dict[str, Any]:
    cache = paths.dist / "flood_path.geojson"
    if cache.exists():
        loaded: dict[str, Any] = json.loads(cache.read_text(encoding="utf-8"))
        return loaded
    payload = _build_flood_geojson()
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _build_flood_geojson() -> dict[str, Any]:
    import numpy as np
    import rasterio
    from rasterio.features import shapes
    from rasterio.warp import transform_geom

    source = paths.dist / "scenario_grid" / "reference_v1.0_d30_full_peak_rise.tif"
    if not source.exists():
        return {"type": "FeatureCollection", "features": []}
    with rasterio.open(source) as dataset:
        band = dataset.read(1)
        crs = dataset.crs
        transform = dataset.transform
    bands = [(0.05, 1.0), (1.0, 2.5), (2.5, 100.0)]
    collected: list[dict[str, Any]] = []
    for low, high in bands:
        mask = ((band > low) & (band <= high)).astype(np.uint8)
        if not mask.any():
            continue
        for geometry, value in shapes(mask, mask=mask.astype(bool), transform=transform):
            if not value:
                continue
            collected.append(
                {
                    "type": "Feature",
                    "geometry": transform_geom(crs, "EPSG:4326", geometry),
                    "properties": {"depth_min_m": low, "depth_max_m": high},
                }
            )
    return {"type": "FeatureCollection", "features": collected}
