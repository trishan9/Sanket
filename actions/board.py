from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.board import AUTONOMOUS_CEILING, LEVEL_ORDER, Level, requires_approval, write_status
from core.state import State
from core.state import state as default_state

__all__ = [
    "AUTONOMOUS_CEILING",
    "LEVEL_ORDER",
    "Level",
    "board_snapshot",
    "requires_approval",
    "write_status",
]


def board_snapshot(basin_id: str | None = None, store: State | None = None) -> dict[str, Any]:
    target = store or default_state
    statuses = target.statuses(basin_id)
    runs = target.runs(limit=10)
    heartbeat = target.last_heartbeat()
    worst: Level = "NORMAL"
    for row in statuses:
        level: Level = row["level"]
        if LEVEL_ORDER[level] > LEVEL_ORDER[worst]:
            worst = level
    return {
        "corridor_level": worst,
        "settlements": statuses,
        "runs": runs,
        "last_checked": heartbeat["at"] if heartbeat else None,
        "generated_at": datetime.now(UTC).isoformat(),
    }
