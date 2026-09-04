from __future__ import annotations

from agent.decision import (
    ALERT_THRESHOLD,
    WATCH_THRESHOLD,
    DecisionInputs,
    decide,
    flip_points,
)


def test_decision_score_matches_direct_computation() -> None:
    inputs = DecisionInputs(
        change_magnitude_z=3.4,
        min_lead_time_minutes=14,
        exposure_count=916,
        confidence="medium",
        vetoed=False,
    )
    decision = decide(inputs)
    expected = sum(c.contribution for c in decision.contributions)
    assert abs(decision.score - expected) < 1e-9
    assert len(decision.contributions) == 4
    assert {c.term for c in decision.contributions} == {
        "change magnitude",
        "minimum lead time",
        "exposure count",
        "confidence",
    }


def test_status_thresholds_are_consistent_with_score() -> None:
    inputs = DecisionInputs(3.4, 14, 916, "medium", False)
    decision = decide(inputs)
    if decision.score >= ALERT_THRESHOLD:
        assert decision.status == "ALERT"
    elif decision.score >= WATCH_THRESHOLD:
        assert decision.status == "WATCH"
    else:
        assert decision.status == "NORMAL"


def test_vetoed_claim_forces_insufficient_with_no_contributions() -> None:
    inputs = DecisionInputs(9.0, 1.0, 100000, "high", True)
    decision = decide(inputs)
    assert decision.status == "INSUFFICIENT"
    assert decision.contributions == ()


def test_higher_z_never_produces_a_lower_status() -> None:
    low = decide(DecisionInputs(0.5, 60, 10, "low", False))
    high = decide(DecisionInputs(5.0, 60, 10, "low", False))
    order = {"NORMAL": 0, "WATCH": 1, "ALERT": 2}
    assert order[high.status] >= order[low.status]


def test_flip_point_genuinely_crosses_the_boundary() -> None:
    inputs = DecisionInputs(3.4, 14, 916, "medium", False)
    base_status = decide(inputs).status
    flips = flip_points(inputs)
    z_flip = flips["change_magnitude_z"]
    assert z_flip is not None and z_flip > 0.0
    above = decide(DecisionInputs(z_flip + 1e-2, 14, 916, "medium", False)).status
    below = decide(DecisionInputs(z_flip - 1e-2, 14, 916, "medium", False)).status
    assert above == base_status
    assert below != base_status


def test_flip_point_none_when_unreachable_within_range() -> None:
    inputs = DecisionInputs(9.0, 1.0, 100000, "high", False)
    flips = flip_points(inputs)
    assert flips["min_lead_time_minutes"] is None
