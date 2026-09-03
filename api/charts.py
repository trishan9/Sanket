from __future__ import annotations

import json
from typing import Any

from flask import jsonify

from analysis.eo.lake_series import build_series
from analysis.eo.precip import daily_series_for_month
from analysis.exposure.leadtime import all_lead_times
from analysis.hydro.scenarios import build_grid
from core.config import paths
from core.corridor import load_all_corridors

PUREPU_LOCATION = (85.36, 28.35)
CACHE_FILE = paths.dist / "chart_cache.json"


def _lake_area_series() -> list[dict[str, Any]]:
    observations = build_series(*PUREPU_LOCATION)
    return [
        {
            "acquired": o.acquired.date().isoformat(),
            "area_km2": o.area_km2,
            "obscured": o.obscured,
            "cloud_fraction": round(o.cloud_fraction, 3),
        }
        for o in sorted(observations, key=lambda o: o.acquired)
    ]


def _rainfall_series(year: int, month: int) -> list[dict[str, Any]]:
    series = daily_series_for_month(year, month)
    return [{"date": d.isoformat(), "basin_mean_mm": v} for d, v in sorted(series.items())]


def _lead_time_distribution() -> list[float]:
    corridor = load_all_corridors()["bhotekoshi"]
    cache = paths.dist / f"chainages_{corridor.basin_id}.json"
    if not cache.exists():
        return []
    chainages: dict[str, float] = json.loads(cache.read_text(encoding="utf-8"))
    results = all_lead_times(chainages, build_grid())
    return [r.lead_time_minutes for r in results if r.lead_time_minutes is not None]


def build_chart_cache() -> dict[str, Any]:
    return {
        "lake_area_series": {"location": "Purepu glacier", "observations": _lake_area_series()},
        "rainfall_series": {
            "month": "2026-08",
            "observations": _rainfall_series(2026, 8),
        },
        "lead_time_distribution": {"minutes": _lead_time_distribution()},
    }


def charts() -> Any:
    if not CACHE_FILE.exists():
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(build_chart_cache()), encoding="utf-8")
    return jsonify(json.loads(CACHE_FILE.read_text(encoding="utf-8")))
