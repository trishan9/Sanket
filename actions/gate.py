from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from core.config import settings
from core.errors import CooldownActiveError, GateNotApprovedError, UnauthorisedApproverError
from core.state import State, now_iso
from core.state import state as default_state

Decision = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class GateRecord:
    gate_id: str
    run_id: str
    action: str
    payload: dict[str, Any]
    requested_at: datetime
    deadline: datetime
    decision: Decision
    approved_at: datetime | None
    approver: str | None


def _row_to_record(row: Any) -> GateRecord:
    return GateRecord(
        gate_id=row["gate_id"],
        run_id=row["run_id"],
        action=row["action"],
        payload=json.loads(row["payload"]),
        requested_at=datetime.fromisoformat(row["requested_at"]),
        deadline=datetime.fromisoformat(row["deadline"]),
        decision=row["decision"],
        approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
        approver=row["approver"],
    )


def request_gate(
    run_id: str,
    action: str,
    payload: dict[str, Any],
    evidence_snapshot: dict[str, Any],
    store: State | None = None,
) -> GateRecord:
    target = store or default_state
    gate_id = uuid.uuid4().hex[:12]
    requested_at = datetime.now(UTC)
    deadline = requested_at + timedelta(minutes=settings.gate_deadline_minutes)
    with target._lock, target.connect() as connection:
        connection.execute(
            "INSERT INTO gates (gate_id, run_id, action, payload, requested_at, deadline, "
            "decision, evidence_snapshot) VALUES (?,?,?,?,?,?,'pending',?)",
            (
                gate_id,
                run_id,
                action,
                json.dumps(payload),
                requested_at.isoformat(),
                deadline.isoformat(),
                json.dumps(evidence_snapshot),
            ),
        )
    return GateRecord(
        gate_id, run_id, action, payload, requested_at, deadline, "pending", None, None
    )


def pending_gate_for_run(run_id: str, store: State | None = None) -> GateRecord | None:
    target = store or default_state
    with target.connect() as connection:
        row = connection.execute(
            "SELECT * FROM gates WHERE run_id=? AND decision='pending' "
            "ORDER BY requested_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    return _row_to_record(row) if row else None


def _is_expired(record: GateRecord, at: datetime) -> bool:
    return at > record.deadline


def record_decision(
    run_id: str,
    sender_contact: str,
    approver_contact: str,
    decision: Literal["approved", "rejected"],
    store: State | None = None,
) -> GateRecord:
    target = store or default_state
    record = pending_gate_for_run(run_id, target)
    if record is None:
        raise GateNotApprovedError(f"no pending gate for run {run_id}")
    if sender_contact != approver_contact:
        raise UnauthorisedApproverError(
            f"{sender_contact} is not the registered approver for run {run_id}"
        )
    if _is_expired(record, datetime.now(UTC)):
        raise GateNotApprovedError(f"gate {record.gate_id} expired at {record.deadline}")
    approved_at = now_iso()
    with target._lock, target.connect() as connection:
        connection.execute(
            "UPDATE gates SET decision=?, approved_at=?, approver=? WHERE gate_id=?",
            (decision, approved_at, sender_contact, record.gate_id),
        )
    return GateRecord(
        record.gate_id,
        record.run_id,
        record.action,
        record.payload,
        record.requested_at,
        record.deadline,
        decision,
        datetime.fromisoformat(approved_at),
        sender_contact,
    )


def cooldown_until(settlement: str, channel: str, store: State | None = None) -> datetime | None:
    target = store or default_state
    with target.connect() as connection:
        row = connection.execute(
            "SELECT cooldown_until FROM notifications WHERE settlement=? AND channel=? "
            "AND cooldown_until IS NOT NULL ORDER BY sent_at DESC LIMIT 1",
            (settlement, channel),
        ).fetchone()
    if row is None or row["cooldown_until"] is None:
        return None
    return datetime.fromisoformat(row["cooldown_until"])


def check_cooldown(settlement: str, channel: str, store: State | None = None) -> None:
    until = cooldown_until(settlement, channel, store)
    if until is not None and datetime.now(UTC) < until:
        raise CooldownActiveError(f"{settlement}/{channel} is in cooldown until {until}")


def record_notification(
    settlement: str,
    channel: str,
    contact: str,
    run_id: str,
    delivery_status: str,
    store: State | None = None,
    message_sid: str | None = None,
) -> str:
    target = store or default_state
    notification_id = uuid.uuid4().hex[:12]
    sent_at = now_iso()
    cooldown = (datetime.now(UTC) + timedelta(minutes=settings.cooldown_minutes)).isoformat()
    with target._lock, target.connect() as connection:
        connection.execute(
            "INSERT INTO notifications (notification_id, settlement, channel, contact, "
            "sent_at, run_id, cooldown_until, delivery_status, message_sid) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                notification_id,
                settlement,
                channel,
                contact,
                sent_at,
                run_id,
                cooldown,
                delivery_status,
                message_sid,
            ),
        )
    return notification_id


def update_delivery_status_by_sid(
    message_sid: str, status: str, store: State | None = None
) -> bool:
    target = store or default_state
    with target._lock, target.connect() as connection:
        cursor = connection.execute(
            "UPDATE notifications SET delivery_status=? WHERE message_sid=?",
            (status, message_sid),
        )
        return cursor.rowcount > 0


def update_delivery_status(notification_id: str, status: str, store: State | None = None) -> None:
    target = store or default_state
    with target._lock, target.connect() as connection:
        connection.execute(
            "UPDATE notifications SET delivery_status=? WHERE notification_id=?",
            (status, notification_id),
        )
