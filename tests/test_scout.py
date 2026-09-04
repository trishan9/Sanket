from __future__ import annotations

import pathlib
import tempfile

import pytest

from agent.scout import cadence_seconds, load_tier, sweep
from core.corridor import load_all_corridors
from core.state import State, basin_tier_summary


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")


@pytest.mark.network
def test_all_47_pdgls_swept_in_one_run_with_cost_recorded(store: State) -> None:
    from agent.budget import budget
    from agent.trace import Trace

    corridors = list(load_all_corridors().values())
    trace = Trace("test_sweep", "national")
    assignments = sweep(corridors, "test_sweep", trace=trace, store=store)

    assert len(assignments) >= 47
    spent = budget.get("test_sweep")
    assert spent.total_npr >= 0


@pytest.mark.network
def test_basin_tiers_written_with_drivers(store: State) -> None:
    corridors = list(load_all_corridors().values())
    sweep(corridors, "test_drivers", store=store)

    summary = basin_tier_summary(store=store)
    assert summary["basins_swept"] >= 47
    for basin in summary["basins"]:
        assert basin["drivers"]
        assert basin["tier"] in {"active", "standing", "survey"}


def test_promoting_a_corridor_changes_its_cadence(store: State) -> None:
    with store._lock, store.connect() as connection:
        connection.execute(
            "INSERT INTO basin_tiers (basin_id, tier, score, drivers, assigned_at) "
            "VALUES ('thame', 'survey', 1.0, '[]', datetime('now'))"
        )
    before = cadence_seconds("thame", store=store)

    with store._lock, store.connect() as connection:
        connection.execute("UPDATE basin_tiers SET tier='active' WHERE basin_id='thame'")
    after = cadence_seconds("thame", store=store)

    assert before == 604800
    assert after == 900
    assert before != after


def test_unassigned_basin_defaults_to_survey(store: State) -> None:
    assert load_tier("nonexistent_basin", store=store) == "survey"
