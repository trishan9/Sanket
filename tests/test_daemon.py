from __future__ import annotations

import pathlib
import tempfile
from unittest.mock import patch

import pytest

from analysis.eo.baselines import compute_baseline
from core.corridor import load_all_corridors
from core.state import State
from watch import triggers
from watch.queue import claim_next, enqueue, finish, pending_count, recover_orphaned
from watch.tiers import fingerprint, handoff, run_tier1


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")


@pytest.fixture
def corridor():  # type: ignore[no-untyped-def]
    return load_all_corridors()["bhotekoshi"]


def test_tier0_and_tier1_make_zero_llm_calls(corridor, store: State) -> None:
    with patch("agent.router.Gateway.complete") as mocked:
        triggers.tick(corridor, store)
        run_tier1(corridor, "OPERA_L3_DSWX-S1_V1", store=store)
        run_tier1(corridor, "OPERA_L3_DSWX-S1_V1", store=store)
        mocked.assert_not_called()


def test_fingerprint_is_stable_for_the_same_inputs() -> None:
    a = fingerprint("bhotekoshi_trishuli", "lhende_barrier", "escalation:5")
    b = fingerprint("bhotekoshi_trishuli", "lhende_barrier", "escalation:5")
    c = fingerprint("bhotekoshi_trishuli", "lhende_barrier", "escalation:6")
    assert a == b
    assert a != c


def test_second_run_on_the_same_anomaly_behaves_differently(corridor, store: State) -> None:
    from analysis.eo.changedetect import classify

    baseline = compute_baseline(
        "test",
        "T45RUL",
        "water_area_km2",
        [5.0, 5.2, 4.8, 5.1, 4.9, 5.0, 5.3, 4.7, 5.0, 5.1, 4.9, 5.2, 5.0, 4.8],
    )
    signal = classify(15.0, baseline)

    _, is_new_first = handoff(corridor, "lhende_barrier", signal, store=store)
    _, is_new_second = handoff(corridor, "lhende_barrier", signal, store=store)

    assert is_new_first is True
    assert is_new_second is False

    with store.connect() as connection:
        row = connection.execute("SELECT growth_history FROM anomalies").fetchone()
    import json

    assert len(json.loads(row["growth_history"])) == 2


def test_killing_and_restarting_recovers_the_queue(corridor, store: State) -> None:
    job_id = enqueue(corridor.basin_id, "investigate", {"anomaly_id": "anom_x"}, store=store)
    claimed = claim_next(corridor.basin_id, store=store)
    assert claimed is not None and claimed.job_id == job_id
    assert pending_count(store=store) == 0

    with store.connect() as connection:
        connection.execute(
            "UPDATE work_queue SET claimed_at=? WHERE job_id=?",
            ("2020-01-01T00:00:00+00:00", job_id),
        )
    recovered = recover_orphaned(store=store, after_minutes=1)
    assert recovered == 1
    assert pending_count(store=store) == 1

    reclaimed = claim_next(corridor.basin_id, store=store)
    assert reclaimed is not None and reclaimed.job_id == job_id
    assert reclaimed.attempts == 2
    finish(job_id, "done", store=store)


def test_missed_ticks_query_cmr_from_last_checked_not_from_now(corridor, store: State) -> None:
    first = triggers.check_granules(corridor, store)
    assert all(g.checked_from is None for g in first)
    second = triggers.check_granules(corridor, store)
    assert all(g.checked_from is not None for g in second)
