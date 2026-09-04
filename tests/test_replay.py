from __future__ import annotations

import pathlib
import tempfile
from datetime import UTC, date, datetime

import pytest

from core.corridor import load_all_corridors
from core.state import State
from watch.replay import (
    ReplayClock,
    _features_newly_due,
    build_clock,
    build_replay_snapshot,
    run_replay,
    verify_replay_checksums,
)


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")


def test_replay_corridor_loads_and_is_marked_as_replay() -> None:
    corridors = load_all_corridors()
    corridor = corridors["bhotekoshi.replay"]
    assert corridor.mode == "replay"
    assert corridor.replay is not None
    assert corridor.basin_id != corridors["bhotekoshi"].basin_id


def test_live_corridors_exclude_the_replay_corridor() -> None:
    corridors = load_all_corridors()
    live = [c for c in corridors.values() if c.mode == "live"]
    assert all(c.mode == "live" for c in live)
    assert "bhotekoshi.replay" not in {k for k, c in corridors.items() if c.mode == "live"}


def test_replay_clock_starts_at_clock_start() -> None:
    corridor = load_all_corridors()["bhotekoshi.replay"]
    clock = build_clock(corridor)
    assert clock.as_of() == date(2026, 8, 27)
    assert clock.speed == 3600.0


def test_replay_clock_finishes_after_elapsing_past_clock_end() -> None:
    clock = ReplayClock(
        clock_start=datetime(2026, 8, 27, 6, 0, tzinfo=UTC),
        clock_end=datetime(2026, 8, 27, 6, 0, 1, tzinfo=UTC),
        speed=3600.0,
        real_start=datetime.now(UTC),
    )
    assert clock.finished() or clock.as_of() == date(2026, 8, 27)


def test_lhende_barrier_is_due_on_the_first_tick_only() -> None:
    corridor = load_all_corridors()["bhotekoshi.replay"]
    first = _features_newly_due(corridor, date(2026, 8, 27), None)
    assert "lhende_barrier" in first
    second = _features_newly_due(corridor, date(2026, 8, 27), date(2026, 8, 27))
    assert "lhende_barrier" not in second


def test_replay_manifest_checksums_verify_against_the_real_granules() -> None:
    manifest = build_replay_snapshot(date(2026, 8, 28))
    assert len(manifest.files) > 0
    mismatches = verify_replay_checksums(manifest)
    assert mismatches == []


def test_detect_water_change_respects_as_of_cutoff(store: State) -> None:
    from agent.tools.catalog import ToolContext, detect_water_change

    ctx = ToolContext("test_firewall", date(2026, 8, 27), store)
    evidence = detect_water_change({"tile": "T45RUL"}, ctx)
    acquired = datetime.fromisoformat(evidence.value["acquired"]).date()
    assert acquired <= date(2026, 8, 27)


def test_detect_water_change_finds_more_recent_data_with_a_later_as_of(store: State) -> None:
    from agent.tools.catalog import ToolContext, detect_water_change

    early_ctx = ToolContext("test_firewall_early", date(2026, 6, 1), store)
    late_ctx = ToolContext("test_firewall_late", date(2026, 9, 3), store)
    early = detect_water_change({"tile": "T45RUL"}, early_ctx)
    late = detect_water_change({"tile": "T45RUL"}, late_ctx)
    early_acquired = datetime.fromisoformat(early.value["acquired"]).date()
    late_acquired = datetime.fromisoformat(late.value["acquired"]).date()
    assert early_acquired <= date(2026, 6, 1)
    assert late_acquired > early_acquired


@pytest.mark.network
def test_full_chain_runs_end_to_end_from_replay_with_no_human_input(store: State) -> None:
    corridor = load_all_corridors()["bhotekoshi.replay"]
    summary = run_replay(corridor, "test_replay_chain", store=store, tick_real_seconds=1.0)

    assert len(summary.ticks) >= 1
    investigated = [t for t in summary.ticks if t.run_id is not None]
    assert investigated

    run_id = investigated[0].run_id
    assert run_id is not None
    from agent.trace import read_trace

    lines = read_trace(run_id)
    assert lines
    assert all(line.replay is True for line in lines)
    kinds = {line.kind for line in lines}
    assert "VERIFY" in kinds
    assert "EXPLAIN" in kinds
    assert "ACTION" in kinds
    assert any(line.kind == "TOOL" for line in lines)
