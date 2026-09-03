from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS basin_tiers (
    basin_id TEXT PRIMARY KEY, tier TEXT NOT NULL, score REAL NOT NULL,
    drivers TEXT NOT NULL DEFAULT '[]', assigned_at TEXT NOT NULL,
    assigned_by_run TEXT
);
CREATE TABLE IF NOT EXISTS baselines (
    product TEXT NOT NULL, tile TEXT NOT NULL, statistic TEXT NOT NULL,
    value REAL NOT NULL, variance REAL NOT NULL, n_obs INTEGER NOT NULL,
    computed_at TEXT NOT NULL, PRIMARY KEY (product, tile, statistic)
);
CREATE TABLE IF NOT EXISTS anomalies (
    anomaly_id TEXT PRIMARY KEY, basin_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
    location TEXT NOT NULL, first_seen TEXT NOT NULL, status TEXT NOT NULL,
    growth_history TEXT NOT NULL DEFAULT '[]', last_investigated TEXT, next_recheck TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_fingerprint ON anomalies(fingerprint);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, basin_id TEXT NOT NULL, agent TEXT NOT NULL,
    trigger TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'live', started TEXT NOT NULL,
    ended TEXT, steps INTEGER NOT NULL DEFAULT 0, tokens_azure INTEGER NOT NULL DEFAULT 0,
    tokens_groq INTEGER NOT NULL DEFAULT 0, cost_npr REAL NOT NULL DEFAULT 0.0,
    outcome TEXT, degradations TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY, settlement TEXT NOT NULL, channel TEXT NOT NULL,
    contact TEXT NOT NULL, sent_at TEXT, run_id TEXT, approved_by TEXT,
    cooldown_until TEXT, delivery_status TEXT NOT NULL DEFAULT 'queued'
);
CREATE TABLE IF NOT EXISTS gates (
    gate_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, action TEXT NOT NULL,
    payload TEXT NOT NULL, requested_at TEXT NOT NULL, deadline TEXT,
    approved_at TEXT, approver TEXT, decision TEXT NOT NULL DEFAULT 'pending',
    evidence_snapshot TEXT
);
CREATE TABLE IF NOT EXISTS subscribers (
    contact TEXT NOT NULL, channel TEXT NOT NULL, settlement TEXT NOT NULL,
    role TEXT NOT NULL, opted_in_at TEXT NOT NULL, stopped_at TEXT,
    PRIMARY KEY (contact, channel)
);
CREATE TABLE IF NOT EXISTS statuses (
    settlement TEXT NOT NULL, basin_id TEXT NOT NULL, level TEXT NOT NULL,
    lead_time_minutes REAL, confidence TEXT, evidence TEXT NOT NULL DEFAULT '{}',
    run_id TEXT, written_at TEXT NOT NULL, PRIMARY KEY (settlement, basin_id)
);
CREATE TABLE IF NOT EXISTS work_queue (
    job_id TEXT PRIMARY KEY, basin_id TEXT NOT NULL, kind TEXT NOT NULL,
    payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL, claimed_at TEXT, finished_at TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS granule_checks (
    basin_id TEXT NOT NULL, product TEXT NOT NULL, last_checked TEXT NOT NULL,
    PRIMARY KEY (basin_id, product)
);
CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT, basin_id TEXT NOT NULL,
    at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _migrate(connection: sqlite3.Connection) -> None:
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(notifications)")}
    if "message_sid" not in columns:
        connection.execute("ALTER TABLE notifications ADD COLUMN message_sid TEXT")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_message_sid ON notifications(message_sid)"
    )


class State:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or paths.state_db
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            _migrate(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def write_status(
        self,
        settlement: str,
        basin_id: str,
        level: str,
        *,
        lead_time_minutes: float | None = None,
        confidence: str | None = None,
        evidence: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO statuses (settlement, basin_id, level, lead_time_minutes, "
                "confidence, evidence, run_id, written_at) VALUES (?,?,?,?,?,?,?,?) "
                "ON CONFLICT(settlement, basin_id) DO UPDATE SET level=excluded.level, "
                "lead_time_minutes=excluded.lead_time_minutes, confidence=excluded.confidence, "
                "evidence=excluded.evidence, run_id=excluded.run_id, "
                "written_at=excluded.written_at",
                (
                    settlement,
                    basin_id,
                    level,
                    lead_time_minutes,
                    confidence,
                    json.dumps(evidence or {}),
                    run_id,
                    now_iso(),
                ),
            )

    def statuses(self, basin_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM statuses"
        params: tuple[Any, ...] = ()
        if basin_id:
            query += " WHERE basin_id = ?"
            params = (basin_id,)
        with self.connect() as connection:
            rows = connection.execute(query + " ORDER BY lead_time_minutes", params).fetchall()
        return [dict(row) | {"evidence": json.loads(row["evidence"])} for row in rows]

    def start_run(
        self, run_id: str, basin_id: str, agent: str, trigger: str, mode: str = "live"
    ) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO runs (run_id, basin_id, agent, trigger, mode, started) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, basin_id, agent, trigger, mode, now_iso()),
            )

    def finish_run(
        self,
        run_id: str,
        *,
        steps: int,
        tokens_azure: int,
        tokens_groq: int,
        cost_npr: float,
        outcome: str,
        degradations: list[str] | None = None,
    ) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "UPDATE runs SET ended=?, steps=?, tokens_azure=?, tokens_groq=?, cost_npr=?, "
                "outcome=?, degradations=? WHERE run_id=?",
                (
                    now_iso(),
                    steps,
                    tokens_azure,
                    tokens_groq,
                    cost_npr,
                    outcome,
                    json.dumps(degradations or []),
                    run_id,
                ),
            )

    def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def heartbeat(self, basin_id: str, note: str = "") -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO heartbeats (basin_id, at, note) VALUES (?,?,?)",
                (basin_id, now_iso(), note),
            )

    def last_heartbeat(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM heartbeats ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def orphan_running_runs(self) -> int:
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET outcome='orphaned', ended=? WHERE ended IS NULL", (now_iso(),)
            )
            return int(cursor.rowcount)


state = State()


def basin_tier_summary(store: State | None = None) -> dict[str, object]:
    target = store or state
    with target.connect() as connection:
        rows = connection.execute(
            "SELECT basin_id, tier, score, drivers, assigned_at FROM basin_tiers "
            "ORDER BY assigned_at DESC"
        ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["tier"]] = counts.get(row["tier"], 0) + 1
    last_swept = rows[0]["assigned_at"] if rows else None
    return {
        "basins_swept": len(rows),
        "tier_counts": counts,
        "last_swept_at": last_swept,
        "basins": [dict(row) for row in rows],
    }
