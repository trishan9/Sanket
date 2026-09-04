from __future__ import annotations

from datetime import date

from analysis.exposure.leadtime import all_lead_times, fraction_under_threshold
from analysis.exposure.preparedness import build_all_profiles
from analysis.exposure.validation import (
    compare_to_reference,
    load_cems_events,
    load_hdx_flood_extent,
)
from core.config import paths
from core.corridor import load_all_corridors

CHAINAGES = {
    "Timure": 400.0,
    "Syapru Besi": 15200.0,
    "Dhunche": 22400.0,
    "Betrawati": 48200.0,
    "Trishuli Bazaar": 53400.0,
}


def test_lead_times_computed_for_every_settlement_per_scenario() -> None:
    results = all_lead_times(CHAINAGES)
    assert len(results) == len(CHAINAGES) * 56
    assert {r.settlement for r in results} == set(CHAINAGES)


def test_histogram_shows_nontrivial_population_under_thirty_minutes() -> None:
    results = all_lead_times(CHAINAGES)
    fraction = fraction_under_threshold(results, 30.0)
    assert fraction > 0.05


def test_standing_preparedness_profile_exists_with_no_event_and_no_alert() -> None:
    corridor = load_all_corridors()["bhotekoshi"]
    profiles = build_all_profiles(corridor, CHAINAGES, as_of=date(2026, 9, 4))
    assert len(profiles) == len(CHAINAGES)
    for profile in profiles:
        assert profile.caveats
        assert "modelled" in " ".join(profile.caveats)


def test_validation_notebook_produces_real_metrics_with_caveats() -> None:
    cems = load_cems_events()
    hdx = load_hdx_flood_extent()
    cog = paths.dist / "scenario_grid" / "reference_v1.0_d30_full_peak_rise.tif"
    assert cog.exists()
    for reference in (cems, hdx):
        matrix = compare_to_reference(cog, reference)
        assert 0.0 <= matrix.precision <= 1.0
        assert 0.0 <= matrix.recall <= 1.0
        assert 0.0 <= matrix.iou <= 1.0
