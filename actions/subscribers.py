from __future__ import annotations

from core.state import State, now_iso
from core.state import state as default_state


def opt_in(
    contact: str, channel: str, settlement: str, role: str, store: State | None = None
) -> None:
    target = store or default_state
    with target._lock, target.connect() as connection:
        connection.execute(
            "INSERT INTO subscribers (contact, channel, settlement, role, opted_in_at, "
            "stopped_at) VALUES (?,?,?,?,?,NULL) "
            "ON CONFLICT(contact, channel) DO UPDATE SET settlement=excluded.settlement, "
            "role=excluded.role, opted_in_at=excluded.opted_in_at, stopped_at=NULL",
            (contact, channel, settlement, role, now_iso()),
        )


def stop(contact: str, channel: str, store: State | None = None) -> None:
    target = store or default_state
    with target._lock, target.connect() as connection:
        connection.execute(
            "UPDATE subscribers SET stopped_at=? WHERE contact=? AND channel=?",
            (now_iso(), contact, channel),
        )


def is_subscribed(contact: str, channel: str, store: State | None = None) -> bool:
    target = store or default_state
    with target.connect() as connection:
        row = connection.execute(
            "SELECT stopped_at FROM subscribers WHERE contact=? AND channel=?",
            (contact, channel),
        ).fetchone()
    return row is not None and row["stopped_at"] is None


def list_subscribers(settlement: str, channel: str, store: State | None = None) -> tuple[str, ...]:
    target = store or default_state
    with target.connect() as connection:
        rows = connection.execute(
            "SELECT contact FROM subscribers WHERE settlement=? AND channel=? "
            "AND stopped_at IS NULL",
            (settlement, channel),
        ).fetchall()
    return tuple(row["contact"] for row in rows)
