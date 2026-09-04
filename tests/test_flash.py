from __future__ import annotations

import pathlib
import tempfile
import time
from datetime import UTC, datetime, timedelta

import pytest

from actions import gate
from core.corridor import load_all_corridors
from core.state import State
from watch.flash import (
    FLASH_GATE_DEADLINE_MINUTES,
    FLASH_LABEL,
    FLASH_MAX_STEPS,
    assess,
    disturbance_jump_trigger,
    escalate_unanswered_gate,
    is_escalation_due,
    rainfall_intensity_trigger,
    stage_rate_trigger,
)


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "flash.sqlite")


@pytest.fixture
def corridor():  # type: ignore[no-untyped-def]
    return load_all_corridors()["bhotekoshi"]


def test_stage_rate_spike_reaches_a_gate_request_in_under_sixty_seconds(corridor, store) -> None:
    started = time.monotonic()
    triggers = (stage_rate_trigger(0.9, 30.0),)
    assessment = assess(corridor, triggers)
    assert assessment.fired
    record = gate.request_gate(
        "flash_run",
        "release_alert",
        payload={"status": assessment.level, "fast_path": True},
        evidence_snapshot={"triggers": [t.kind for t in triggers]},
        store=store,
    )
    elapsed = time.monotonic() - started
    assert record.gate_id
    assert elapsed < 60.0


def test_reduced_step_budget_is_smaller_than_the_normal_loop() -> None:
    from agent.loop import MAX_STEPS

    assert FLASH_MAX_STEPS == 4
    assert FLASH_MAX_STEPS < MAX_STEPS


def test_two_independent_triggers_reach_red_one_reaches_orange(corridor) -> None:
    one = assess(corridor, (stage_rate_trigger(0.9, 30.0),))
    two = assess(
        corridor,
        (stage_rate_trigger(0.9, 30.0), rainfall_intensity_trigger(60.0, 60.0)),
    )
    assert one.level == "ORANGE"
    assert two.level == "RED"


def test_quiet_triggers_do_not_fire_the_fast_path(corridor) -> None:
    assessment = assess(corridor, (stage_rate_trigger(0.01, 30.0), disturbance_jump_trigger(0.0)))
    assert assessment.fired is False
    assert assessment.level == "GREEN"


def test_fast_path_is_labelled_in_every_rendered_string(corridor) -> None:
    triggers = (stage_rate_trigger(0.9, 30.0), disturbance_jump_trigger(0.9))
    assessment = assess(corridor, triggers)
    assert FLASH_LABEL in assessment.rendered()
    for trigger in triggers:
        assert FLASH_LABEL in trigger.rendered()


def test_fast_path_carries_its_own_reduced_confidence_tier(corridor) -> None:
    assessment = assess(corridor, (stage_rate_trigger(0.9, 30.0),))
    assert "reduced" in assessment.confidence_tier
    assert "fast path" in assessment.confidence_tier


def test_gate_deadline_is_shorter_than_the_standard_gate() -> None:
    from core.config import settings

    assert settings.gate_deadline_minutes > FLASH_GATE_DEADLINE_MINUTES


def test_auto_escalation_fires_on_deadline_and_is_logged(store) -> None:
    stale = datetime.now(UTC) - timedelta(minutes=FLASH_GATE_DEADLINE_MINUTES + 1)
    assert is_escalation_due(stale) is True
    notification_id = escalate_unanswered_gate("flash_run", stale, store=store)
    assert notification_id
    with store.connect() as connection:
        row = connection.execute(
            "SELECT settlement, delivery_status FROM notifications WHERE notification_id=?",
            (notification_id,),
        ).fetchone()
    assert row["settlement"] == "flash_gate_escalation"
    assert row["delivery_status"] == "escalated_unanswered"


def test_escalation_does_not_fire_before_the_deadline(store) -> None:
    fresh = datetime.now(UTC)
    assert is_escalation_due(fresh) is False
    assert escalate_unanswered_gate("flash_run", fresh, store=store) is None
