from __future__ import annotations

import re
from typing import Any, Literal

from actions import gate, subscribers, whatsapp
from core.contacts import approver
from core.errors import GateNotApprovedError, UnauthorisedApproverError
from core.state import State

APPROVE_PATTERN = re.compile(r"^\s*APPROVE\s+([A-Za-z0-9_]+)\s*$", re.IGNORECASE)
REJECT_PATTERN = re.compile(r"^\s*REJECT\s+([A-Za-z0-9_]+)\s*$", re.IGNORECASE)
STOP_PATTERN = re.compile(r"^\s*STOP\s*$", re.IGNORECASE)


def handle_inbound(from_contact: str, body: str, store: State | None = None) -> dict[str, Any]:
    text = body.strip()
    if STOP_PATTERN.match(text):
        subscribers.stop(from_contact, "whatsapp", store=store)
        return {"action": "stop", "contact": from_contact}
    approve_match = APPROVE_PATTERN.match(text)
    if approve_match:
        return _handle_decision(approve_match.group(1), from_contact, "approved", store)
    reject_match = REJECT_PATTERN.match(text)
    if reject_match:
        return _handle_decision(reject_match.group(1), from_contact, "rejected", store)
    return {"action": "ignored", "contact": from_contact, "body": text}


def _handle_decision(
    run_id: str,
    from_contact: str,
    decision: Literal["approved", "rejected"],
    store: State | None,
) -> dict[str, Any]:
    try:
        record = gate.record_decision(
            run_id, from_contact, approver().contact, decision, store=store
        )
    except UnauthorisedApproverError as exc:
        return {"action": "unauthorised", "run_id": run_id, "reason": str(exc)}
    except GateNotApprovedError as exc:
        return {"action": "no_pending_gate", "run_id": run_id, "reason": str(exc)}
    result: dict[str, Any] = {"action": decision, "run_id": run_id, "gate_id": record.gate_id}
    if decision == "approved":
        outcomes = whatsapp.release_from_gate(record, store=store)
        result["released"] = len(outcomes)
    return result


def handle_status_callback(message_sid: str, status: str, store: State | None = None) -> bool:
    return gate.update_delivery_status_by_sid(message_sid, status, store=store)
