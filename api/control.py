from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from flask import jsonify, request

from actions import gate as gate_module
from actions import whatsapp
from core.config import settings
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


DRILL_LIVE_CORRIDOR = "bhotekoshi"
DRILL_LEVELS: tuple[str, ...] = ("ORANGE", "RED")


def _lead_time_for(corridor_key: str, settlement: str) -> float | None:
    from analysis.exposure.preparedness import build_all_profiles
    from api.preparedness import _load_chainages

    corridor = load_all_corridors()[corridor_key]
    chainages = _load_chainages(corridor.basin_id)
    if not chainages:
        return None
    for profile in build_all_profiles(corridor, chainages, as_of=datetime.now(UTC).date()):
        if profile.settlement == settlement:
            return profile.minimum_lead_time_minutes
    return None


def drill_alert() -> Any:
    from actions.alertcard import render_alert_card
    from actions.channels.twilio_whatsapp import TwilioWhatsApp
    from actions.levels import RISK_ENGLISH_ACTION, RISK_NEPALI_ACTION, coerce_level

    body = request.get_json(silent=True) or {}
    settlement = str(body.get("settlement", "Timure")).strip()
    raw_level = str(body.get("level", "RED")).strip().upper()
    if raw_level not in DRILL_LEVELS:
        return jsonify({"error": f"level must be one of {list(DRILL_LEVELS)}"}), 400
    try:
        registered = approver().contact
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 503

    corridor = load_all_corridors()[DRILL_LIVE_CORRIDOR]
    if settlement not in corridor.settlement_names:
        return jsonify({"error": f"unknown settlement {settlement}"}), 400

    level = coerce_level(raw_level)
    run_id = f"drill_alert_{uuid.uuid4().hex[:8]}"
    lead = _lead_time_for(DRILL_LIVE_CORRIDOR, settlement)
    card = render_alert_card(
        corridor, settlement, level, run_id, lead_time_minutes=lead, replay=True
    )
    image_url = f"{settings.public_base_url.rstrip('/')}/alertcards/{card.path.name}"
    lead_line = f"Estimated arrival {lead:.0f} min." if lead is not None else ""
    text = (
        f"[DRILL - NOT A REAL ALERT] SANKET {level} for {settlement}. {lead_line} "
        f"{RISK_ENGLISH_ACTION[level]} {RISK_NEPALI_ACTION[level]} "
        f"Channel and map render test, run {run_id}."
    )
    result = TwilioWhatsApp().send_media(registered, text, image_url)
    gate_module.record_notification(
        "drill", "whatsapp", registered, run_id, result.status,
        store=default_state, message_sid=result.message_sid or None,
    )
    return _drill_alert_payload(
        run_id, settlement, level, lead, image_url, card, result, registered
    )


def _drill_alert_payload(
    run_id: str,
    settlement: str,
    level: str,
    lead: float | None,
    image_url: str,
    card: Any,
    result: Any,
    registered: str,
) -> Any:
    return jsonify(
        {
            "run_id": run_id,
            "settlement": settlement,
            "level": level,
            "lead_time_minutes": lead,
            "image_url": image_url,
            "card_file": card.path.name,
            "delivery_status": result.status,
            "message_sid": result.message_sid,
            "error": result.error,
            "contact": registered,
        }
    )


def _record_drill(drill_id: str, **fields: Any) -> None:
    with _drill_lock:
        _drills[drill_id].update(fields)


def _execute_drill(drill_id: str, prefix: str, instant: bool) -> None:
    from watch.replay import run_replay

    started = datetime.now(UTC)
    try:
        corridor = load_all_corridors()[DRILL_CORRIDOR]
        summary = run_replay(
            corridor,
            prefix,
            store=default_state,
            tick_real_seconds=DRILL_TICK_SECONDS,
            deterministic=instant,
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
    body = request.get_json(silent=True) or {}
    instant = bool(body.get("instant"))
    drill_id = uuid.uuid4().hex[:8]
    prefix = f"drill_{drill_id}"
    with _drill_lock:
        _drills[drill_id] = {
            "drill_id": drill_id,
            "prefix": prefix,
            "state": "running",
            "started_at": datetime.now(UTC).isoformat(),
            "corridor": DRILL_CORRIDOR,
            "mode": "deterministic" if instant else "adaptive",
        }
    thread = threading.Thread(target=_execute_drill, args=(drill_id, prefix, instant), daemon=True)
    thread.start()
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
