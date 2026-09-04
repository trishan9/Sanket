from __future__ import annotations

import re

import pytest

from actions.escalation import EscalationInput, classify_stage, decide, ladder
from analysis.risk.prediction import (
    INDICATORS,
    estimate_hazard,
    prior_rate_per_lake_year,
)
from analysis.risk.rootcause import attribute
from core.corridor import load_all_corridors

ALARM = {
    "seismic_landslide_type": True,
    "upstream_mass_movement": True,
    "radar_water_anomaly": True,
    "antecedent_precip_extreme": False,
}

FORBIDDEN = (
    r"will fail",
    r"will burst",
    r"will breach",
    r"is certain to",
    r"guaranteed",
)


@pytest.fixture
def corridor():  # type: ignore[no-untyped-def]
    return load_all_corridors()["bhotekoshi"]


def test_prior_comes_from_the_measured_base_rate() -> None:
    median, low, high = prior_rate_per_lake_year("moraine")
    assert low <= median <= high
    assert 0 < median < 0.01


def test_evidence_raises_the_estimate_and_absence_lowers_it() -> None:
    quiet = estimate_hazard("lake", "moraine", {"radar_water_anomaly": False}, 30)
    loud = estimate_hazard("lake", "moraine", {"radar_water_anomaly": True}, 30)
    assert loud.posterior_probability > quiet.posterior_probability
    assert quiet.lift < 1.0
    assert loud.lift > 1.0


def test_unobserved_indicators_move_nothing() -> None:
    blind = estimate_hazard("lake", "moraine", {}, 30)
    assert blind.lift == pytest.approx(1.0, abs=1e-9)
    assert len(blind.unobserved) == len(INDICATORS)


def test_a_formed_dam_uses_the_survival_prior_not_the_inventory_rate() -> None:
    fresh = estimate_hazard(
        "lhende_barrier", "landslide_debris", {}, 7, already_formed=True, days_since_formation=1.0
    )
    assert fresh.prior_probability > 0.1
    assert "Costa and Schuster" in " ".join(fresh.steps)


def test_a_dam_that_has_held_for_weeks_carries_lower_forward_probability() -> None:
    fresh = estimate_hazard(
        "dam", "landslide_debris", {}, 7, already_formed=True, days_since_formation=1.0
    )
    weathered = estimate_hazard(
        "dam", "landslide_debris", {}, 7, already_formed=True, days_since_formation=60.0
    )
    assert weathered.posterior_probability < fresh.posterior_probability


def test_credible_interval_brackets_the_point_estimate() -> None:
    estimate = estimate_hazard("dam", "landslide_debris", ALARM, 7, already_formed=True)
    low, high = estimate.credible_interval
    assert low <= estimate.posterior_probability <= high


def test_dominant_indicator_is_the_strongest_observed_one() -> None:
    estimate = estimate_hazard("dam", "landslide_debris", ALARM, 7, already_formed=True)
    assert estimate.dominant_indicator == "seismic_landslide_type"


def test_no_hazard_string_claims_certainty() -> None:
    estimate = estimate_hazard("dam", "landslide_debris", ALARM, 7, already_formed=True)
    text = " ".join([estimate.rendered(), *estimate.steps, *estimate.caveats]).lower()
    for pattern in FORBIDDEN:
        assert not re.search(pattern, text), f"{pattern!r} appeared in hazard output"
    assert "not a statement about a specific date" in estimate.rendered()


def test_every_indicator_carries_a_citation() -> None:
    for indicator in INDICATORS:
        assert indicator.citation.strip()
        assert indicator.likelihood_ratio_present > 0
        assert indicator.likelihood_ratio_absent > 0


def test_attribution_separates_candidates_on_their_own_evidence(corridor) -> None:
    result = attribute(
        corridor,
        "Timure",
        {
            "lhende_barrier": ALARM,
            "purepu_glacier": {"seismic_landslide_type": False, "lake_area_growth": True},
        },
        7,
    )
    assert result.leading is not None
    assert result.leading.node_id == "lhende_barrier"
    barrier = next(c for c in result.candidates if c.node_id == "lhende_barrier")
    glacier = next(c for c in result.candidates if c.node_id == "purepu_glacier")
    assert barrier.supporting != glacier.supporting
    assert any("seismic" in item.lower() for item in barrier.supporting)
    assert any("seismic" in item.lower() for item in glacier.contradicting)


def test_attribution_never_claims_established_causation(corridor) -> None:
    result = attribute(corridor, "Timure", {"lhende_barrier": ALARM}, 7)
    text = " ".join([result.rendered(), *result.caveats]).lower()
    assert "not established causation" in text or "does not establish" in text


def test_escalation_walks_grey_to_orange_to_red_then_stands_down() -> None:
    stages = []
    previous = None
    for signal in (
        EscalationInput(1, 0.08, False, False),
        EscalationInput(3, 0.55, False, False),
        EscalationInput(3, 0.92, True, False),
        EscalationInput(0, 0.01, False, False),
    ):
        result = decide(signal, previous)
        stages.append((result.stage, result.level, result.autonomous))
        previous = result.stage
    assert stages[0] == ("early_advisory", "GREY", True)
    assert stages[1] == ("corroborated", "ORANGE", False)
    assert stages[2] == ("verified", "RED", False)
    assert stages[3] == ("stand_down", "GREEN", True)


def test_the_early_advisory_is_the_only_escalating_stage_sent_without_a_human() -> None:
    for stage in ladder():
        if stage["stage"] in {"corroborated", "verified"}:
            assert stage["autonomous"] is False, f"{stage['stage']} must hold at the gate"
        if stage["stage"] == "early_advisory":
            assert stage["autonomous"] is True


def test_a_veto_drops_back_to_an_advisory_rather_than_alerting() -> None:
    result = decide(EscalationInput(3, 0.95, False, True), "corroborated")
    assert result.stage == "early_advisory"
    assert result.level == "GREY"
    assert "veto" in result.reason.lower()


def test_stage_classification_is_threshold_driven_not_arbitrary() -> None:
    below, _ = classify_stage(EscalationInput(1, 0.10, False, False))
    above, _ = classify_stage(EscalationInput(1, 0.30, False, False))
    assert below == "early_advisory"
    assert above == "corroborated"


def test_every_stage_carries_a_nepali_headline() -> None:
    for stage in ladder():
        assert str(stage["headline_nepali"]).strip()
