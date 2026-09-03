from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from agent.router import Lane, gateway
from agent.trace import Trace
from analysis.eo.national_sweep import BasinFeatures, build_basin_features, coarse_priority_score
from core.connectors.icimod import read_pdgl
from core.corridor import Corridor
from core.state import State, now_iso
from core.state import state as default_state

Tier = Literal["active", "standing", "survey"]
SCOUT_LANE: Lane = "sanket-scout"

SCOUT_SYSTEM_PROMPT = (
    "You are Scout, sweeping all potentially dangerous glacial lakes in Nepal's Koshi, "
    "Gandaki and Karnali basins once a week. For each lake you are given a rank (ICIMOD "
    "danger rank I/II/III), area, elevation, and a historical GLOF recurrence count for "
    "its country from HMAGLOFDB. Assign exactly one tier to each: 'active' (check every "
    "15 minutes - reserve for the few most urgent), 'standing' (check every 6 hours), or "
    "'survey' (check weekly - the default for most). Respond with strict JSON only: a "
    "list of objects with keys 'gl_id', 'tier', 'driver' (one short sentence explaining "
    "the assignment). No prose outside the JSON."
)

TIER_CADENCE_SECONDS: dict[Tier, int] = {"active": 900, "standing": 21600, "survey": 604800}


@dataclass(frozen=True)
class TierAssignment:
    basin_id: str
    tier: Tier
    score: float
    driver: str


def _feature_summary(feature: BasinFeatures) -> dict[str, object]:
    return {
        "gl_id": feature.gl_id,
        "country": feature.country,
        "rank": feature.rank,
        "area_km2": round(feature.area_km2, 3),
        "elevation_m": round(feature.elevation_m),
        "recurrence_count": feature.recurrence_count,
        "coarse_score": round(coarse_priority_score(feature), 2),
    }


def _coerce_tier(raw: str) -> Tier:
    valid: dict[str, Tier] = {"active": "active", "standing": "standing", "survey": "survey"}
    return valid.get(raw, "survey")


def _parse_response(content: str, features: list[BasinFeatures]) -> dict[str, TierAssignment]:
    by_id = {f.gl_id: f for f in features}
    text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    parsed = json.loads(text)
    assignments: dict[str, TierAssignment] = {}
    for item in parsed:
        gl_id = str(item.get("gl_id", ""))
        feature = by_id.get(gl_id)
        if feature is None:
            continue
        tier = _coerce_tier(str(item.get("tier", "survey")))
        assignments[gl_id] = TierAssignment(
            basin_id=gl_id,
            tier=tier,
            score=coarse_priority_score(feature),
            driver=str(item.get("driver", "")),
        )
    return assignments


def _fallback_assignments(features: list[BasinFeatures]) -> dict[str, TierAssignment]:
    ranked = sorted(features, key=coarse_priority_score, reverse=True)
    assignments: dict[str, TierAssignment] = {}
    for index, feature in enumerate(ranked):
        tier: Tier = "active" if index < 2 else "standing" if index < 10 else "survey"
        assignments[feature.gl_id] = TierAssignment(
            basin_id=feature.gl_id,
            tier=tier,
            score=coarse_priority_score(feature),
            driver=f"fallback ranking: rank {feature.rank}, "
            f"{feature.recurrence_count} historical GLOFs in {feature.country}",
        )
    return assignments


def _store_tiers(assignments: dict[str, TierAssignment], run_id: str, store: State) -> None:
    with store._lock, store.connect() as connection:
        for basin_id, assignment in assignments.items():
            connection.execute(
                "INSERT INTO basin_tiers (basin_id, tier, score, drivers, assigned_at, "
                "assigned_by_run) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(basin_id) DO UPDATE SET tier=excluded.tier, "
                "score=excluded.score, drivers=excluded.drivers, "
                "assigned_at=excluded.assigned_at, assigned_by_run=excluded.assigned_by_run",
                (
                    basin_id,
                    assignment.tier,
                    assignment.score,
                    json.dumps([assignment.driver]),
                    now_iso(),
                    run_id,
                ),
            )


def _query_scout(
    features: list[BasinFeatures], run_id: str, trace: Trace | None
) -> dict[str, TierAssignment]:
    payload = json.dumps([_feature_summary(f) for f in features])
    messages = [
        {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
        {"role": "user", "content": payload},
    ]
    try:
        response = gateway.complete(
            SCOUT_LANE, messages, run_id=run_id, trace=trace, use_cache=False, max_tokens=4000
        )
        assignments = _parse_response(response["content"] or "", features)
        if len(assignments) < len(features) // 2:
            raise ValueError("Scout returned too few valid assignments")
        return assignments
    except Exception as exc:
        if trace is not None:
            trace.degraded(f"Scout LLM sweep failed ({type(exc).__name__}), using fallback ranking")
        return _fallback_assignments(features)


def _force_live_corridors_active(
    assignments: dict[str, TierAssignment], live_corridors: list[Corridor]
) -> None:
    for corridor in live_corridors:
        if corridor.basin_id not in assignments:
            assignments[corridor.basin_id] = TierAssignment(
                basin_id=corridor.basin_id,
                tier="active",
                score=999.0,
                driver="live corridor, forced to active tier regardless of PDGL status",
            )


def sweep(
    live_corridors: list[Corridor],
    run_id: str,
    trace: Trace | None = None,
    store: State | None = None,
) -> dict[str, TierAssignment]:
    target = store or default_state
    pdgl = read_pdgl()
    features = build_basin_features(pdgl)
    if trace is not None:
        trace.trigger(f"weekly sweep · {len(features)} PDGLs")

    assignments = _query_scout(features, run_id, trace)
    _force_live_corridors_active(assignments, live_corridors)
    _store_tiers(assignments, run_id, target)
    if trace is not None:
        counts: dict[str, int] = {}
        for a in assignments.values():
            counts[a.tier] = counts.get(a.tier, 0) + 1
        trace.done(f"swept {len(features)} PDGLs · tiers: {counts}")
    return assignments


def load_tier(basin_id: str, store: State | None = None) -> Tier:
    target = store or default_state
    with target.connect() as connection:
        row = connection.execute(
            "SELECT tier FROM basin_tiers WHERE basin_id=?", (basin_id,)
        ).fetchone()
    return row["tier"] if row else "survey"


def cadence_seconds(basin_id: str, store: State | None = None) -> int:
    tier = load_tier(basin_id, store)
    return TIER_CADENCE_SECONDS[tier]
