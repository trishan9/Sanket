from __future__ import annotations

import json
from typing import Any

from flask import jsonify

from actions.escalation import STAGE_LEVEL, ladder
from analysis.risk.observability import observability_report
from analysis.risk.susceptibility import rank_pdgls
from core.corridor import load_all_corridors
from core.state import state as default_state

RECENT_LIMIT = 25


def _rows(query: str, limit: int) -> list[dict[str, Any]]:
    with default_state.connect() as connection:
        return [dict(row) for row in connection.execute(query, (limit,))]


def _recent_runs() -> list[dict[str, Any]]:
    runs = _rows(
        "SELECT run_id, basin_id, agent, trigger, mode, started, ended, steps, "
        "tokens_azure, tokens_groq, cost_npr, outcome, degradations "
        "FROM runs ORDER BY started DESC LIMIT ?",
        RECENT_LIMIT,
    )
    for run in runs:
        try:
            run["degradations"] = json.loads(str(run.get("degradations") or "[]"))
        except json.JSONDecodeError:
            run["degradations"] = []
    return runs


def alert_history() -> Any:
    notifications = _rows(
        "SELECT notification_id, settlement, channel, contact, sent_at, run_id, "
        "delivery_status, approved_by FROM notifications ORDER BY sent_at DESC LIMIT ?",
        RECENT_LIMIT,
    )
    gates = _rows(
        "SELECT gate_id, run_id, action, requested_at, deadline, approved_at, approver, "
        "decision FROM gates ORDER BY requested_at DESC LIMIT ?",
        RECENT_LIMIT,
    )
    runs = _recent_runs()
    statuses = _rows(
        "SELECT settlement, basin_id, level, lead_time_minutes, confidence, written_at, run_id "
        "FROM statuses ORDER BY lead_time_minutes LIMIT ?",
        RECENT_LIMIT,
    )
    heartbeat = _rows("SELECT basin_id, at, note FROM heartbeats ORDER BY id DESC LIMIT ?", 1)
    return jsonify(
        {
            "stages": list(ladder()),
            "notifications": notifications,
            "gates": gates,
            "runs": runs,
            "statuses": statuses,
            "last_heartbeat": heartbeat[0] if heartbeat else None,
            "channel_counts": _channel_counts(notifications),
            "current_levels": {
                str(row["settlement"]): str(row["level"]) for row in statuses
            },
            "stage_levels": dict(STAGE_LEVEL),
        }
    )


def _channel_counts(notifications: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in notifications:
        key = str(row.get("channel") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def hotzones() -> Any:
    corridor = load_all_corridors()["bhotekoshi"]
    statuses = {
        str(row["settlement"]): row for row in default_state.statuses(corridor.basin_id)
    }
    features = []
    for station in corridor.downstream_reach:
        status = statuses.get(station.name, {})
        lead = status.get("lead_time_minutes")
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(station.location)},
                "properties": {
                    "name": station.name,
                    "district": station.district,
                    "level": status.get("level", "INSUFFICIENT"),
                    "lead_time_minutes": lead,
                    "confidence": status.get("confidence"),
                    "severity": _severity(lead),
                },
            }
        )
    return jsonify({"type": "FeatureCollection", "features": features})


def _severity(lead_time_minutes: float | None) -> float:
    if lead_time_minutes is None:
        return 0.15
    if lead_time_minutes <= 15:
        return 1.0
    if lead_time_minutes <= 45:
        return 0.72
    if lead_time_minutes <= 90:
        return 0.45
    return 0.25


def national_risk() -> Any:
    scores = rank_pdgls()
    report = observability_report("Koshi")
    bands: dict[str, int] = {}
    for score in scores:
        bands[score.band] = bands.get(score.band, 0) + 1
    return jsonify(
        {
            "ranked_count": len(scores),
            "bands": bands,
            "top": [
                {
                    "node_id": score.node_id,
                    "band": score.band,
                    "rank_score": round(score.rank_score, 4),
                }
                for score in scores[:12]
            ],
            "observability": {
                "inventoried_lakes": report.inventoried_lakes,
                "below_detection_limit": report.below_detection_limit,
                "detection_limit_km2": report.detection_limit_km2,
            },
        }
    )
