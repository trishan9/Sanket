from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from core.state import State, now_iso
from core.state import state as default_state

JobKind = Literal["investigate"]
JobState = Literal["pending", "claimed", "done", "failed", "orphaned"]

ORPHAN_AFTER_MINUTES = 30


@dataclass(frozen=True)
class InvestigationJob:
    job_id: str
    basin_id: str
    kind: JobKind
    payload: dict[str, Any]
    state: JobState
    created_at: datetime
    claimed_at: datetime | None
    attempts: int


def _row_to_job(row: Any) -> InvestigationJob:
    return InvestigationJob(
        job_id=row["job_id"],
        basin_id=row["basin_id"],
        kind=row["kind"],
        payload=json.loads(row["payload"]),
        state=row["state"],
        created_at=datetime.fromisoformat(row["created_at"]),
        claimed_at=datetime.fromisoformat(row["claimed_at"]) if row["claimed_at"] else None,
        attempts=row["attempts"],
    )


def enqueue(
    basin_id: str, kind: JobKind, payload: dict[str, Any], store: State | None = None
) -> str:
    target = store or default_state
    job_id = uuid.uuid4().hex[:12]
    with target._lock, target.connect() as connection:
        connection.execute(
            "INSERT INTO work_queue (job_id, basin_id, kind, payload, state, created_at) "
            "VALUES (?,?,?,?,'pending',?)",
            (job_id, basin_id, kind, json.dumps(payload), now_iso()),
        )
    return job_id


def claim_next(basin_id: str | None = None, store: State | None = None) -> InvestigationJob | None:
    target = store or default_state
    with target._lock, target.connect() as connection:
        query = "SELECT * FROM work_queue WHERE state='pending'"
        params: tuple[Any, ...] = ()
        if basin_id is not None:
            query += " AND basin_id=?"
            params = (basin_id,)
        query += " ORDER BY created_at LIMIT 1"
        row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE work_queue SET state='claimed', claimed_at=?, attempts=attempts+1 "
            "WHERE job_id=?",
            (now_iso(), row["job_id"]),
        )
        refreshed = connection.execute(
            "SELECT * FROM work_queue WHERE job_id=?", (row["job_id"],)
        ).fetchone()
    return _row_to_job(refreshed)


def finish(job_id: str, outcome: JobState, store: State | None = None) -> None:
    target = store or default_state
    with target._lock, target.connect() as connection:
        connection.execute(
            "UPDATE work_queue SET state=?, finished_at=? WHERE job_id=?",
            (outcome, now_iso(), job_id),
        )


def recover_orphaned(
    store: State | None = None, *, after_minutes: int = ORPHAN_AFTER_MINUTES
) -> int:
    target = store or default_state
    cutoff = (datetime.now(UTC) - timedelta(minutes=after_minutes)).isoformat()
    with target._lock, target.connect() as connection:
        cursor = connection.execute(
            "UPDATE work_queue SET state='pending', claimed_at=NULL "
            "WHERE state='claimed' AND claimed_at < ?",
            (cutoff,),
        )
        return int(cursor.rowcount)


def pending_count(basin_id: str | None = None, store: State | None = None) -> int:
    target = store or default_state
    with target.connect() as connection:
        if basin_id is None:
            row = connection.execute(
                "SELECT count(*) FROM work_queue WHERE state='pending'"
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT count(*) FROM work_queue WHERE state='pending' AND basin_id=?",
                (basin_id,),
            ).fetchone()
    return int(row[0])
