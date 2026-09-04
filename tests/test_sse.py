from __future__ import annotations

import json
import pathlib
import tempfile
import threading
import time

from agent.trace import Trace
from api.sse import stream_trace_lines
from core.config import paths as core_paths


def _emit_with_delay(trace: Trace, delay: float) -> None:
    trace.watch("first line")
    time.sleep(delay)
    trace.watch("second line")
    time.sleep(delay)
    trace.done("finished")


def test_sse_streams_incrementally_not_all_at_once() -> None:
    directory = pathlib.Path(tempfile.mkdtemp())
    trace = Trace("test_sse_run", "bhotekoshi_trishuli", directory=directory)
    delay = 0.6
    thread = threading.Thread(target=_emit_with_delay, args=(trace, delay))
    thread.start()

    events: list[tuple[float, dict[str, object]]] = []
    started = time.monotonic()
    for event in stream_trace_lines("test_sse_run", timeout_seconds=10, directory=directory):
        payload = json.loads(event.removeprefix("data: ").strip())
        events.append((time.monotonic() - started, payload))
        if payload["kind"] == "DONE":
            break
    thread.join()

    assert [e[1]["kind"] for e in events] == ["WATCH", "WATCH", "DONE"]
    assert events[1][0] - events[0][0] >= delay * 0.5
    assert events[2][0] - events[1][0] >= delay * 0.5


def test_sse_response_sets_streaming_headers() -> None:
    from api.app import create_app

    app = create_app()
    directory = pathlib.Path(tempfile.mkdtemp())
    trace = Trace("test_sse_headers", "bhotekoshi_trishuli", directory=directory)
    trace.trigger("start")
    trace.done("end")

    original_directory = core_paths.trace
    core_paths.trace = directory
    try:
        with app.test_client() as client:
            response = client.get("/api/trace/test_sse_headers/stream")
            assert response.mimetype == "text/event-stream"
            assert response.headers["X-Accel-Buffering"] == "no"
            body = response.get_data(as_text=True)
    finally:
        core_paths.trace = original_directory

    assert "TRIGGER" in body
    assert "DONE" in body
