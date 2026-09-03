from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from flask import jsonify

from analysis.exposure.preparedness import PreparednessProfile, build_all_profiles
from core.config import paths
from core.corridor import load_all_corridors


def _load_chainages(basin_id: str) -> dict[str, float]:
    cache = paths.dist / f"chainages_{basin_id}.json"
    if not cache.exists():
        return {}
    data: dict[str, float] = json.loads(cache.read_text(encoding="utf-8"))
    return data


def _serialize(profile: PreparednessProfile) -> dict[str, Any]:
    return {
        "settlement": profile.settlement,
        "district": profile.district,
        "minimum_lead_time_minutes": profile.minimum_lead_time_minutes,
        "maximum_lead_time_minutes": profile.maximum_lead_time_minutes,
        "population": round(profile.exposure.population),
        "buildings": profile.exposure.buildings,
        "bridges": profile.exposure.bridges,
        "bridges_at_risk": profile.isolation.bridges_at_risk,
        "single_point_of_failure": profile.isolation.single_point_of_failure,
        "dem_vintage": profile.dem_vintage,
        "generated_as_of": profile.generated_as_of.isoformat(),
        "caveats": list(profile.caveats),
    }


def preparedness() -> Any:
    corridors = load_all_corridors()
    live = {k: c for k, c in corridors.items() if c.mode == "live"}
    payload: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(), "corridors": {}}
    for key, corridor in live.items():
        chainages = _load_chainages(corridor.basin_id)
        if not chainages:
            payload["corridors"][key] = {"available": False, "reason": "chainages not cached"}
            continue
        profiles = build_all_profiles(corridor, chainages, as_of=datetime.now(UTC).date())
        payload["corridors"][key] = {
            "available": True,
            "basin_id": corridor.basin_id,
            "profiles": [_serialize(p) for p in profiles],
        }
    return jsonify(payload)
