from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from flask import jsonify, request

from actions import gate as gate_module
from actions import whatsapp
from core.contacts import approver
from core.corridor import load_all_corridors
from core.errors import ConfigError, GateNotApprovedError, UnauthorisedApproverError
from core.state import state as default_state

Decision = Literal["approved", "rejected"]
DECISIONS: tuple[Decision, ...] = ("approved", "rejected")
DRILL_CORRIDOR = "bhotekoshi.replay"
DRILL_TICK_SECONDS = 0.05

_drills: dict[str, dict[str, Any]] = {}
_drill_lock = threading.Lock()


def _gate_row(record: gate_module.GateRecord) -> dict[str, Any]:
    payload = record.payload
    remaining = (record.deadline - datetime.now(UTC)).total_seconds()
    return {
        "gate_id": record.gate_id,
        "run_id": record.run_id,
        "action": record.action,
        "status": payload.get("status"),
        "requested_at": record.requested_at.isoformat(),
        "deadline": record.deadline.isoformat(),
        "seconds_remaining": round(max(remaining, 0.0)),
        "expired": remaining <= 0,
        "decision": record.decision,
        "institutional_body": payload.get("institutional_body"),
        "image_url": payload.get("image_url"),
        "resident_bodies": payload.get("resident_bodies", {}),
        "resident_images": payload.get("resident_images", {}),
        "decision_score": payload.get("decision_score"),
        "contributions": payload.get("contributions", []),
        "counterfactuals": payload.get("counterfactuals", []),
        "flip_points": payload.get("flip_points", []),
        "what_would_change_my_mind": payload.get("what_would_change_my_mind", []),
        "provenance_links": payload.get("provenance_links", []),
    }


def _pending_records() -> list[gate_module.GateRecord]:
    with default_state.connect() as connection:
        rows = connection.execute(
            "SELECT run_id FROM gates WHERE decision='pending' ORDER BY requested_at DESC"
        ).fetchall()
    records = [gate_module.pending_gate_for_run(str(row[0])) for row in rows]
    return [record for record in records if record is not None]


def pending_gates() -> Any:
    try:
        registered = approver().contact
    except ConfigError:
        registered = None
    return jsonify(
        {
            "approver": registered,
            "pending": [_gate_row(record) for record in _pending_records()],
        }
    )


def _release(record: gate_module.GateRecord) -> list[dict[str, str]]:
    return [
        {
            "tier": outcome.tier,
            "contact": outcome.contact,
            "settlement": outcome.settlement,
            "status": outcome.result.status,
            "message_sid": outcome.result.message_sid,
        }
        for outcome in whatsapp.release_from_gate(record, store=default_state)
    ]


def gate_decision(run_id: str) -> Any:
    body = request.get_json(silent=True) or {}
    raw = str(body.get("decision", "")).strip().lower()
    contact = str(body.get("approver", "")).strip()
    decision = next((item for item in DECISIONS if item == raw), None)
    if decision is None:
        return jsonify({"error": "decision must be approved or rejected"}), 400
    if not contact:
        return jsonify({"error": "approver contact is required"}), 400
    try:
        registered = approver().contact
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 503
    try:
        record = gate_module.record_decision(
            run_id, contact, registered, decision, store=default_state
        )
    except UnauthorisedApproverError as exc:
        return jsonify({"error": str(exc), "reason": "unauthorised"}), 403
    except GateNotApprovedError as exc:
        return jsonify({"error": str(exc), "reason": "no_pending_gate"}), 409
    released = _release(record) if decision == "approved" else []
    return jsonify(
        {
            "run_id": run_id,
            "gate_id": record.gate_id,
            "decision": decision,
            "approved_at": record.approved_at.isoformat() if record.approved_at else None,
            "approver": record.approver,
            "released": released,
        }
    )


def _record_drill(drill_id: str, **fields: Any) -> None:
    with _drill_lock:
        _drills[drill_id].update(fields)


def _execute_drill(drill_id: str, prefix: str) -> None:
    from watch.replay import run_replay

    started = datetime.now(UTC)
    try:
        corridor = load_all_corridors()[DRILL_CORRIDOR]
        summary = run_replay(
            corridor, prefix, store=default_state, tick_real_seconds=DRILL_TICK_SECONDS
        )
    except Exception as exc:
        _record_drill(drill_id, state="failed", error=f"{type(exc).__name__}: {exc}")
        return
    runs = [tick.run_id for tick in summary.ticks if tick.run_id]
    _record_drill(
        drill_id,
        state="finished",
        finished_at=datetime.now(UTC).isoformat(),
        elapsed_seconds=round((datetime.now(UTC) - started).total_seconds(), 1),
        ticks=len(summary.ticks),
        investigated=sum(1 for tick in summary.ticks if tick.outcome == "investigated"),
        handoffs=sum(1 for tick in summary.ticks if tick.outcome == "handoff"),
        run_ids=runs,
        latest_run_id=runs[-1] if runs else None,
    )


def start_drill() -> Any:
    drill_id = uuid.uuid4().hex[:8]
    prefix = f"drill_{drill_id}"
    with _drill_lock:
        _drills[drill_id] = {
            "drill_id": drill_id,
            "prefix": prefix,
            "state": "running",
            "started_at": datetime.now(UTC).isoformat(),
            "corridor": DRILL_CORRIDOR,
            "mode": "replay",
        }
    threading.Thread(target=_execute_drill, args=(drill_id, prefix), daemon=True).start()
    return jsonify({"drill_id": drill_id, "state": "running", "prefix": prefix}), 202


def drill_status(drill_id: str) -> Any:
    with _drill_lock:
        record = _drills.get(drill_id)
        payload = dict(record) if record else None
    if payload is None:
        return jsonify({"error": f"no drill {drill_id}"}), 404
    if payload["state"] == "finished":
        prefix = str(payload["prefix"])
        matched = [r for r in _pending_records() if r.run_id.startswith(prefix)]
        payload["pending_gates"] = [_gate_row(record) for record in matched]
    return jsonify(payload)
