from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from core.config import paths

_SCHEMA = """
CREATE TABLE IF NOT EXISTS response_cache (
    key TEXT PRIMARY KEY,
    lane TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def cache_key(lane: str, messages: list[dict[str, Any]], tools: Any = None) -> str:
    payload = json.dumps(
        {"lane": lane, "messages": messages, "tools": tools}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class ResponseCache:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (paths.data / "cache.sqlite")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=10)

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM response_cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        loaded: dict[str, Any] = json.loads(row[0])
        return loaded

    def put(self, key: str, lane: str, payload: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO response_cache (key, lane, payload) VALUES (?, ?, ?)",
                (key, lane, json.dumps(payload, default=str)),
            )

    def size(self) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT count(*) FROM response_cache").fetchone()
        return int(row[0])


response_cache = ResponseCache()
