from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

from flask import Response, stream_with_context

from agent.trace import TraceLine, read_trace
from core.config import settings

POLL_SECONDS = 0.5
TERMINAL_KINDS = frozenset({"DONE", "ERROR"})


def _sse_event(line: TraceLine) -> str:
    payload = json.loads(line.model_dump_json())
    return f"data: {json.dumps(payload)}\n\n"


def stream_trace_lines(
    run_id: str, *, timeout_seconds: int | None = None, directory: Path | None = None
) -> Iterator[str]:
    sent = 0
    deadline = time.monotonic() + (timeout_seconds or settings.run_timeout_seconds)
    while time.monotonic() < deadline:
        lines = read_trace(run_id, directory)
        for line in lines[sent:]:
            yield _sse_event(line)
            sent += 1
        if lines and lines[-1].kind in TERMINAL_KINDS:
            return
        time.sleep(POLL_SECONDS)


def trace_stream_response(run_id: str) -> Response:
    response = Response(
        stream_with_context(stream_trace_lines(run_id)), mimetype="text/event-stream"
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
