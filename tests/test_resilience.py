from __future__ import annotations

import pathlib
import tempfile
from datetime import date
from unittest.mock import patch

import pytest

from agent.deterministic import run_deterministic_investigation
from agent.ledger import Claim, Ledger
from agent.loop import investigate
from agent.tools.catalog import ToolContext
from agent.trace import Trace
from agent.verifier import detect_contradiction
from analysis.eo.baselines import compute_baseline
from analysis.eo.changedetect import classify
from core.corridor import load_all_corridors
from core.errors import AllProvidersFailedError, ConnectorError
from core.state import State
from watch import worker
from watch.daemon import tick
from watch.queue import enqueue
from watch.tiers import run_tier2

CONSTANT_HISTORY = [5.0, 5.2, 4.8, 5.1, 4.9, 5.0, 5.3, 4.7, 5.0, 5.1, 4.9, 5.2, 5.0, 4.8]


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")


@pytest.fixture
def corridor():  # type: ignore[no-untyped-def]
    return load_all_corridors()["bhotekoshi"]


def test_tier2_classify_degrades_to_conservative_investigate_when_no_provider(corridor) -> None:
    baseline = compute_baseline("test", "T45RUL", "water_area_km2", CONSTANT_HISTORY)
    signal = classify(15.0, baseline)
    trace = Trace("test_tier2_degraded", corridor.basin_id)
    with patch("agent.router.Gateway.complete", side_effect=AllProvidersFailedError("forced")):
        classification = run_tier2(signal, "test_tier2_degraded", trace=trace)
    assert classification == "investigate"
    assert any(line.kind == "DEGRADED" for line in trace.lines)


def test_verifier_contradiction_check_degrades_when_no_provider() -> None:
    ledger = Ledger("test_verifier_degraded", date(2026, 9, 3))
    claim = Claim(statement="a claim to check for contradiction", claim_type="observation")
    fake_result = type(
        "R", (), {"chunks": [type("C", (), {"text": "some retrieved science text"})()]}
    )()
    with (
        patch("agent.verifier.retrieve", return_value=fake_result),
        patch("agent.router.Gateway.complete", side_effect=AllProvidersFailedError("forced")),
    ):
        result = detect_contradiction(claim, ledger, "test_verifier_degraded")
    assert result.passed is True
    assert "deterministic mode" in result.detail


def test_deterministic_investigation_gathers_real_evidence_and_concludes(corridor) -> None:
    run_id = "test_deterministic_direct"
    as_of = date(2026, 8, 28)
    ledger = Ledger(run_id, as_of)
    scratch = State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")
    ctx = ToolContext(run_id, as_of, scratch)
    trace = Trace(run_id, corridor.basin_id)
    run_deterministic_investigation(corridor, "lhende_barrier", ctx, ledger, trace)
    assert ledger.claims
    assert ledger.outcome.concluded
    assert any(line.kind == "DEGRADED" for line in trace.lines)
    assert any(e.claim_type == "scenario" for e in ledger.evidence) or any(
        e.claim_type == "model_output" for e in ledger.evidence
    )


def test_investigate_falls_back_to_deterministic_mode_when_no_provider(
    corridor, store: State
) -> None:
    run_id = "test_investigate_degraded"
    trace = Trace(run_id, corridor.basin_id)
    with patch("agent.router.Gateway.complete", side_effect=AllProvidersFailedError("forced")):
        ledger = investigate(
            corridor,
            "anom_test",
            "lhende_barrier",
            {"source": "test"},
            run_id,
            trace,
            store=store,
            as_of=date(2026, 8, 28),
        )
    assert ledger.claims
    assert ledger.outcome.concluded
    assert any(
        line.kind == "DEGRADED" and "deterministic mode" in line.message for line in trace.lines
    )


def test_opera_search_wraps_network_failures_in_connector_error() -> None:
    from core.connectors import opera

    with (
        patch("earthaccess.search_data", side_effect=ConnectionError("simulated outage")),
        pytest.raises(ConnectorError),
    ):
        opera.search("OPERA_L3_DSWX-S1_V1", (85.10, 27.80, 85.45, 28.55))


def test_worker_drains_a_queued_investigation_and_records_a_run(corridor, store: State) -> None:
    payload = {"anomaly_id": "anom_x", "feature_id": "lhende_barrier"}
    enqueue(corridor.basin_id, "investigate", payload, store=store)

    fake_ledger = Ledger("fake", date(2026, 8, 28))
    fake_ledger.escalate(None, "fake escalation for test")
    with (
        patch("watch.worker.investigate", return_value=fake_ledger),
        patch("watch.worker.run_verifier_explainer_actor"),
    ):
        run_id = worker.process_one(corridor, store=store)

    assert run_id is not None
    runs = store.runs(limit=5)
    assert any(r["run_id"] == run_id and r["agent"] == "investigator" for r in runs)


def test_daemon_tick_drains_pending_investigations(corridor, store: State) -> None:
    payload = {"anomaly_id": "anom_y", "feature_id": "lhende_barrier"}
    enqueue(corridor.basin_id, "investigate", payload, store=store)
    fake_ledger = Ledger("fake2", date(2026, 8, 28))
    fake_ledger.escalate(None, "fake escalation for test")
    with (
        patch("watch.worker.investigate", return_value=fake_ledger),
        patch("watch.worker.run_verifier_explainer_actor"),
    ):
        result = tick(corridor, store)
    assert result["outcome"] == "investigated"
    assert result["investigations"]
