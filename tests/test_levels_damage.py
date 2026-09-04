from __future__ import annotations

import re

import pytest

from actions.levels import (
    RISK_LEVELS,
    SettlementLevel,
    apply_hysteresis,
    coerce_level,
    requires_approval,
    to_legacy,
    worst,
)
from analysis.economics.damage import (
    NOT_MONETISED,
    damage_fraction_for_depth,
    estimate_damage,
)


def test_old_level_names_still_resolve() -> None:
    assert coerce_level("NORMAL") == "GREEN"
    assert coerce_level("WATCH") == "YELLOW"
    assert coerce_level("ALERT") == "RED"
    assert coerce_level("INSUFFICIENT") == "GREY"
    for level in RISK_LEVELS:
        assert coerce_level(level) == level


def test_orange_is_the_new_level() -> None:
    assert "ORANGE" in RISK_LEVELS
    assert coerce_level("ORANGE") == "ORANGE"
    assert to_legacy("ORANGE") == "ALERT"


def test_settlements_hold_different_levels_simultaneously() -> None:
    held = [
        SettlementLevel("Timure", "RED", "2 min lead time"),
        SettlementLevel("Syapru Besi", "ORANGE", "22 min lead time"),
        SettlementLevel("Dhunche", "YELLOW", "38 min lead time"),
        SettlementLevel("Betrawati", "GREEN", "no modelled arrival"),
        SettlementLevel("Trishuli Bazaar", "GREY", "cloud blocked, cannot assess"),
    ]
    levels = {item.level for item in held}
    assert len(levels) == 5
    assert worst([item.level for item in held]) == "RED"


def test_grey_is_an_honest_state_not_an_escalation() -> None:
    assert requires_approval("GREY") is False
    assert requires_approval("GREEN") is False
    assert requires_approval("YELLOW") is False
    assert requires_approval("ORANGE") is True
    assert requires_approval("RED") is True


def test_hysteresis_is_one_way_within_an_event() -> None:
    assert apply_hysteresis("RED", "YELLOW", within_event=True) == "RED"
    assert apply_hysteresis("YELLOW", "RED", within_event=True) == "RED"
    assert apply_hysteresis("RED", "GREEN", within_event=False) == "GREEN"


def test_unknown_level_is_refused() -> None:
    with pytest.raises(ValueError):
        coerce_level("PURPLE")


def test_damage_is_always_a_range_never_a_point_estimate() -> None:
    for depth in (0.2, 0.8, 1.5, 2.4, 5.0):
        damage = estimate_damage("Syapru Besi", depth, buildings=357, bridges=1)
        assert damage.high_npr > damage.low_npr
        rendered = damage.rendered()
        assert "-" in rendered
        singleton = re.search(r"damage NPR ([\d.]+) million(?!\s*-)", rendered)
        assert singleton is None, f"point estimate emitted: {rendered}"


def test_damage_lists_assumptions_and_cites_unit_cost_sources() -> None:
    damage = estimate_damage("Timure", 2.0, buildings=40, bridges=1)
    assert damage.assumptions
    joined = " ".join(damage.assumptions).lower()
    assert "replacement" in joined
    assert "npr per usd" in joined
    assert any("Nepal" in source for source in damage.assumptions)


def test_every_damage_figure_says_life_is_not_monetised() -> None:
    damage = estimate_damage("Dhunche", 1.2, buildings=120, bridges=0)
    assert NOT_MONETISED in damage.rendered()
    assert NOT_MONETISED in damage.caveats


def test_depth_damage_fraction_increases_with_depth() -> None:
    fractions = [damage_fraction_for_depth(d) for d in (0.2, 0.8, 1.5, 2.5, 6.0)]
    assert fractions == sorted(fractions)
    assert fractions[-1] <= 1.0
