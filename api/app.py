from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geolibre
from flask import Flask, jsonify, send_from_directory

from actions.board import board_snapshot
from agent.trace import list_runs, read_trace
from api.agents import agents, chain_trace, full_chain_runs
from api.charts import charts
from api.control import (
    drill_alert,
    drill_status,
    flood_card,
    gate_decision,
    pending_gates,
    start_drill,
)
from api.fallback import fallback_page
from api.operations import alert_history, hotzones, national_risk
from api.predict import (
    escalation_ladder,
    escalation_simulate,
    indicators,
    map_layers,
    predict,
    rootcause,
)
from api.preparedness import preparedness
from api.risk import (
    cascade,
    completeness,
    damage,
    met,
    observability,
    scenario_matrix,
    susceptibility,
    validation,
)
from api.sse import trace_stream_response
from api.webhooks import ask_sandbox, gate_screen, twilio_inbound, twilio_status_callback
from core.config import paths
from core.corridor import load_all_corridors

GEOLIBRE_APP_DIR = Path(geolibre.__file__).resolve().parent / "static" / "app"

PROGRESS_FILE = paths.root / "progress.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def corridor_payload() -> dict[str, Any]:
    return {
        key: {
            "basin_id": c.basin_id,
            "name": c.name,
            "districts": list(c.districts),
            "settlements": list(c.settlement_names),
            "authority": c.authority.body,
            "dem_vintage": c.dem_vintage.isoformat(),
            "mode": c.mode,
        }
        for key, c in load_all_corridors().items()
    }


def trace_payload(run_id: str) -> dict[str, Any]:
    lines = read_trace(run_id)
    return {
        "run_id": run_id,
        "lines": [json.loads(line.model_dump_json()) for line in lines],
        "rendered": [line.render() for line in lines],
    }


def health() -> Any:
    return jsonify({"status": "ok", "service": "sanket"})


def status() -> Any:
    return jsonify(board_snapshot())


def status_for(basin_id: str) -> Any:
    return jsonify(board_snapshot(basin_id))


def corridors() -> Any:
    return jsonify(corridor_payload())


def progress() -> Any:
    return jsonify(_read_json(PROGRESS_FILE))


def runs() -> Any:
    return jsonify({"runs": list(list_runs())})


def trace(run_id: str) -> Any:
    return jsonify(trace_payload(run_id))


def trace_stream(run_id: str) -> Any:
    return trace_stream_response(run_id)


def national() -> Any:
    from core.state import basin_tier_summary

    return jsonify(basin_tier_summary())


def geolibre_app_root() -> Any:
    return send_from_directory(GEOLIBRE_APP_DIR, "index.html")


def geolibre_app_asset(filename: str) -> Any:
    return send_from_directory(GEOLIBRE_APP_DIR, filename)


def alert_card(filename: str) -> Any:
    return send_from_directory(paths.dist / "alertcards", filename)


def dist_data(filename: str) -> Any:
    return send_from_directory(paths.dist, filename)


GET_ROUTES: tuple[tuple[str, Any], ...] = (
    ("/api/health", health),
    ("/api/status", status),
    ("/api/status/<basin_id>", status_for),
    ("/api/corridors", corridors),
    ("/api/progress", progress),
    ("/api/runs", runs),
    ("/api/trace/<run_id>", trace),
    ("/api/trace/<run_id>/stream", trace_stream),
    ("/api/national", national),
    ("/api/gate/<run_id>", gate_screen),
    ("/api/preparedness", preparedness),
    ("/api/charts", charts),
    ("/fallback", fallback_page),
    ("/geolibre/", geolibre_app_root),
    ("/geolibre/<path:filename>", geolibre_app_asset),
    ("/data/<path:filename>", dist_data),
    ("/alertcards/<path:filename>", alert_card),
    ("/api/risk/susceptibility", susceptibility),
    ("/api/risk/cascade/<node_id>", cascade),
    ("/api/risk/observability/<catchment>", observability),
    ("/api/risk/scenarios", scenario_matrix),
    ("/api/met/<iso_date>", met),
    ("/api/damage", damage),
    ("/api/validation", validation),
    ("/api/completeness", completeness),
    ("/api/predict/indicators", indicators),
    ("/api/predict/<node_id>", predict),
    ("/api/rootcause/<settlement>", rootcause),
    ("/api/escalation/ladder", escalation_ladder),
    ("/api/escalation/simulate", escalation_simulate),
    ("/api/map/layers", map_layers),
    ("/api/alerts/history", alert_history),
    ("/api/hotzones", hotzones),
    ("/api/national-risk", national_risk),
    ("/api/agents", agents),
    ("/api/agents/runs", full_chain_runs),
    ("/api/agents/trace/<run_id>", chain_trace),
    ("/api/gate", pending_gates),
    ("/api/drill/<drill_id>", drill_status),
    ("/api/floodcard", flood_card),
)

POST_ROUTES: tuple[tuple[str, Any], ...] = (
    ("/webhooks/twilio/inbound", twilio_inbound),
    ("/webhooks/twilio/status", twilio_status_callback),
    ("/api/ask", ask_sandbox),
    ("/api/gate/<run_id>/decision", gate_decision),
    ("/api/drill", start_drill),
    ("/api/drill/alert", drill_alert),
)


def _allow_cors(response: Any) -> Any:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def create_app() -> Flask:
    app = Flask(__name__)
    for rule, handler in GET_ROUTES:
        app.add_url_rule(rule, handler.__name__, handler, methods=["GET"])
    for rule, handler in POST_ROUTES:
        app.add_url_rule(rule, handler.__name__, handler, methods=["POST"])
    app.after_request(_allow_cors)
    return app


app = create_app()
