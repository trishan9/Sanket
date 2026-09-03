from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

from core.config import paths

Agent = Literal["scout", "watcher", "investigator", "verifier", "explainer", "actor", "system"]

Kind = Literal[
    "TRIGGER",
    "MEMORY",
    "WATCH",
    "STEP",
    "TOOL",
    "RETRY",
    "ERROR",
    "VERIFY",
    "EXPLAIN",
    "ACTION",
    "GATE",
    "APPROVED",
    "REJECTED",
    "DEGRADED",
    "DONE",
]

AGENT_OF_KIND: dict[Kind, Agent] = {
    "TRIGGER": "system",
    "MEMORY": "system",
    "WATCH": "watcher",
    "STEP": "investigator",
    "TOOL": "investigator",
    "RETRY": "investigator",
    "ERROR": "system",
    "VERIFY": "verifier",
    "EXPLAIN": "explainer",
    "ACTION": "actor",
    "GATE": "actor",
    "APPROVED": "actor",
    "REJECTED": "actor",
    "DEGRADED": "system",
    "DONE": "system",
}


class TraceLine(BaseModel):
    model_config = ConfigDict(frozen=True)

    ts: datetime
    run_id: str
    basin_id: str
    agent: Agent
    kind: Kind
    message: str
    replay: bool = False
    step: int | None = None
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    provider: str | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_npr: float | None = None
    duration_ms: int | None = None
    failed: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    def render(self) -> str:
        stamp = self.ts.strftime("%H:%M:%S")
        marker = "REPLAY " if self.replay else ""
        head = f"[{stamp}] {marker}{self.kind:<9}"
        body = self.message
        if self.step is not None:
            body = f"step {self.step} · {body}"
        if self.model:
            body = f"[{self.model}] {body}"
        if self.tokens_in is not None or self.tokens_out is not None:
            body += f" · {(self.tokens_in or 0) + (self.tokens_out or 0)} tok"
        if self.cost_npr is not None:
            body += f" · NPR {self.cost_npr:.4f}"
        return head + body


class Trace:
    def __init__(
        self, run_id: str, basin_id: str, *, replay: bool = False, directory: Path | None = None
    ) -> None:
        self.run_id = run_id
        self.basin_id = basin_id
        self.replay = replay
        self._lock = threading.Lock()
        self._directory = directory or paths.trace
        self._directory.mkdir(parents=True, exist_ok=True)
        self.path = self._directory / f"{run_id}.jsonl"
        self._lines: list[TraceLine] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def emit(
        self, kind: Kind, message: str, *, agent: Agent | None = None, **fields: Any
    ) -> TraceLine:
        line = TraceLine(
            ts=datetime.now(UTC),
            run_id=self.run_id,
            basin_id=self.basin_id,
            agent=agent or AGENT_OF_KIND[kind],
            kind=kind,
            message=message,
            replay=self.replay,
            **fields,
        )
        with self._lock:
            self._lines.append(line)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line.model_dump_json() + "\n")
        return line

    def trigger(self, message: str, **f: Any) -> TraceLine:
        return self.emit("TRIGGER", message, **f)

    def memory(self, message: str, **f: Any) -> TraceLine:
        return self.emit("MEMORY", message, **f)

    def watch(self, message: str, **f: Any) -> TraceLine:
        return self.emit("WATCH", message, **f)

    def step(self, index: int, message: str, **f: Any) -> TraceLine:
        return self.emit("STEP", message, step=index, **f)

    def tool(self, name: str, args: dict[str, Any], result: str, **f: Any) -> TraceLine:
        return self.emit(
            "TOOL", f"{name}(...) -> {result}", tool=name, args=args, result=result, **f
        )

    def retry(self, name: str, message: str, **f: Any) -> TraceLine:
        return self.emit("RETRY", message, tool=name, **f)

    def error(self, message: str, **f: Any) -> TraceLine:
        return self.emit("ERROR", message, failed=True, **f)

    def verify(self, message: str, **f: Any) -> TraceLine:
        return self.emit("VERIFY", message, **f)

    def explain(self, message: str, **f: Any) -> TraceLine:
        return self.emit("EXPLAIN", message, **f)

    def action(self, message: str, **f: Any) -> TraceLine:
        return self.emit("ACTION", message, **f)

    def gate(self, message: str, **f: Any) -> TraceLine:
        return self.emit("GATE", message, **f)

    def degraded(self, message: str, **f: Any) -> TraceLine:
        return self.emit("DEGRADED", message, **f)

    def done(self, message: str, **f: Any) -> TraceLine:
        return self.emit("DONE", message, **f)

    @property
    def lines(self) -> tuple[TraceLine, ...]:
        return tuple(self._lines)

    def render(self) -> str:
        return "\n".join(line.render() for line in self._lines)


def read_trace(run_id: str, directory: Path | None = None) -> tuple[TraceLine, ...]:
    path = (directory or paths.trace) / f"{run_id}.jsonl"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as handle:
        return tuple(TraceLine(**json.loads(raw)) for raw in handle if raw.strip())


def list_runs(directory: Path | None = None) -> tuple[str, ...]:
    root = directory or paths.trace
    if not root.exists():
        return ()
    return tuple(sorted(p.stem for p in root.glob("*.jsonl")))
