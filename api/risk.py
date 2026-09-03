from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from flask import jsonify, request

from analysis.economics.damage import estimate_damage
from analysis.met.ruleout import rainfall_explains
from analysis.risk.cascade_sim import simulate_cascade
from analysis.risk.observability import observability_report
from analysis.risk.susceptibility import rank_pdgls
from core.config import paths
from core.corridor import load_all_corridors

VALIDATION_CACHE = paths.dist / "validation_cache.json"
COMPLETENESS_CACHE = paths.dist / "completeness_cache.json"
DEFAULT_TILE = "T45RUL"

SCENARIOS: tuple[tuple[str, str], ...] = (
    ("reference_v1.0_d30_full", "1.0 Mm3 / 30 min"),
    ("v5.0_d360_full", "5.0 Mm3 / 360 min (largest in grid)"),
)


def _serialise_score(score: Any) -> dict[str, Any]:
    return {
        "node_id": score.node_id,
        "rank_score": round(score.rank_score, 4),
        "band": score.band,
        "summary": score.rendered(),
        "base_rates": [
            {
                "stratum": rate.stratum,
                "events": rate.events,
                "population": rate.population,
                "rate_per_lake": rate.rate_per_lake,
                "ci_low": rate.ci_low,
                "ci_high": rate.ci_high,
                "sample_size": rate.sample_size,
                "record_period": rate.record_period,
                "caveat": rate.caveat,
                "rendered": rate.rendered(),
            }
            for rate in score.base_rates
        ],
        "unobservable_parameters": list(score.unobservable_parameters),
        "parameters": [
            {
                "name": p.name,
                "group": p.group,
                "value": p.value,
                "unit": p.unit,
                "source": p.source,
                "observable": p.observable,
                "note": p.note,
            }
            for p in score.parameters
        ],
        "frameworks": list(score.frameworks),
        "caveats": list(score.caveats),
    }


def susceptibility() -> Any:
    scores = rank_pdgls()
    return jsonify(
        {
            "count": len(scores),
            "ranked": [_serialise_score(score) for score in scores],
        }
    )


def cascade(node_id: str) -> Any:
    corridor = load_all_corridors()["bhotekoshi"]
    result = simulate_cascade(corridor, node_id, 1.0)
    return jsonify(
        {
            "origin": result.origin_node_id,
            "summary": result.rendered(),
            "decay_per_step": result.decay_per_step,
            "terminal_confidence": result.terminal_confidence,
            "steps": [
                {
                    "order": step.order,
                    "node_id": step.node_id,
                    "node_type": step.node_type,
                    "mechanism": step.mechanism,
                    "confidence": step.confidence,
                    "note": step.note,
                }
                for step in result.steps
            ],
            "caveats": list(result.caveats),
        }
    )


def observability(catchment: str) -> Any:
    report = observability_report(catchment)
    return jsonify(
        {
            "catchment": report.catchment,
            "inventoried_lakes": report.inventoried_lakes,
            "below_detection_limit": report.below_detection_limit,
            "below_attention_threshold": report.below_attention_threshold,
            "detection_limit_km2": report.detection_limit_km2,
            "attention_threshold_km2": report.attention_threshold_km2,
            "smallest_inventoried_km2": report.smallest_inventoried_km2,
            "summary": report.rendered(),
            "caveats": list(report.caveats),
        }
    )


def met(iso_date: str) -> Any:
    result = rainfall_explains(date.fromisoformat(iso_date))
    return jsonify(
        {
            "date": result.target_date.isoformat(),
            "rainfall_explains": result.explains,
            "daily_percentile": result.daily_percentile,
            "daily_mm": result.daily_mm,
            "monthly_percentile": result.monthly_percentile,
            "monthly_mm": result.monthly_mm,
            "antecedent_mm": result.anomaly.antecedent_mm,
            "antecedent_days": result.anomaly.antecedent_days,
            "seasonal_context": result.anomaly.seasonal_context,
            "unobserved_layers": list(result.anomaly.unobserved_layers),
            "summary": result.rendered(),
            "caveats": list(result.caveats + result.anomaly.notes),
        }
    )


def damage() -> Any:
    settlement = request.args.get("settlement", "Syapru Besi")
    depth = float(request.args.get("depth_m", 1.5))
    buildings = int(request.args.get("buildings", 100))
    bridges = int(request.args.get("bridges", 0))
    result = estimate_damage(settlement, depth, buildings, bridges)
    return jsonify(
        {
            "settlement": result.settlement,
            "depth_m": result.depth_m,
            "damage_fraction": result.damage_fraction,
            "low_npr": result.low_npr,
            "high_npr": result.high_npr,
            "low_usd": result.low_usd,
            "high_usd": result.high_usd,
            "summary": result.rendered(),
            "assumptions": list(result.assumptions),
            "caveats": list(result.caveats),
        }
    )


def _compute_validation() -> dict[str, Any]:
    from analysis.exposure.validation import (
        compare_to_reference,
        load_cems_events,
        load_hdx_flood_extent,
    )

    references = [
        ("CEMS EMSR927", load_cems_events()),
        ("HDX flood extent", load_hdx_flood_extent()),
    ]
    rows: list[dict[str, Any]] = []
    for slug, label in SCENARIOS:
        cog = paths.dist / "scenario_grid" / f"{slug}_peak_rise.tif"
        if not cog.exists():
            continue
        for name, frame in references:
            matrix = compare_to_reference(cog, frame)
            rows.append(
                {
                    "scenario": label,
                    "reference": name,
                    "precision": matrix.precision,
                    "recall": matrix.recall,
                    "iou": matrix.iou,
                    "f1": matrix.f1,
                    "true_positive": matrix.true_positive,
                    "false_positive": matrix.false_positive,
                    "false_negative": matrix.false_negative,
                }
            )
    return {
        "rows": rows,
        "reading": (
            "High precision against the HDX extent with low recall means the modelled corridor "
            "falls inside the observed flood but covers only part of it: a 1D water-only router "
            "on pre-event terrain cannot reproduce a debris-laden event that reworked the valley."
        ),
    }


def validation() -> Any:
    if VALIDATION_CACHE.exists():
        return jsonify(json.loads(VALIDATION_CACHE.read_text(encoding="utf-8")))
    payload = _compute_validation()
    VALIDATION_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return jsonify(payload)


def _month_counts(observations: list[Any]) -> dict[str, int]:
    counter = Counter(o.acquired.strftime("%Y-%m") for o in observations)
    return dict(sorted(counter.items()))


def _compute_completeness() -> dict[str, Any]:
    from analysis.eo.dist import observations_for_tile as dist_obs
    from analysis.eo.dswx import observations_for_tile as dswx_obs

    optical = list(dist_obs(DEFAULT_TILE))
    radar = list(dswx_obs(DEFAULT_TILE))
    return {
        "tile": DEFAULT_TILE,
        "optical": {"product": "OPERA DIST-ALERT-HLS", "by_month": _month_counts(optical)},
        "radar": {"product": "OPERA DSWx-S1", "by_month": _month_counts(radar)},
        "note": (
            "counts are usable granules held locally, not total acquisitions; optical is "
            "cloud-limited through the monsoon, which is the argument for radar"
        ),
    }


def completeness() -> Any:
    if COMPLETENESS_CACHE.exists():
        return jsonify(json.loads(COMPLETENESS_CACHE.read_text(encoding="utf-8")))
    payload = _compute_completeness()
    COMPLETENESS_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return jsonify(payload)


def scenario_matrix() -> Any:
    from analysis.hydro.scenarios import grid_directory

    directory: Path = grid_directory()
    available = sorted(p.stem for p in directory.glob("*.npz"))
    return jsonify({"count": len(available), "scenarios": available})
