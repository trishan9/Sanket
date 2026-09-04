from __future__ import annotations

from analysis.eo.baselines import compute_baseline
from analysis.eo.changedetect import classify
from analysis.eo.dswx import observations_for_tile, water_area_km2
from analysis.eo.lake_series import build_series, cloud_gaps

PUREPU_LON, PUREPU_LAT = 85.36, 28.35


def test_dswx_tile_has_real_observations() -> None:
    observations = observations_for_tile("T45RUL")
    assert len(observations) > 10
    areas = [water_area_km2(obs) for obs in observations]
    assert all(area >= 0 for area in areas)
    assert max(areas) > 0


def test_baseline_has_variance_and_n_obs() -> None:
    observations = observations_for_tile("T45RUL")
    areas = [water_area_km2(obs) for obs in observations]
    baseline = compute_baseline("OPERA_L3_DSWX-S1_V1", "T45RUL", "water_area_km2", areas)
    assert baseline.n_obs >= 3
    assert baseline.variance >= 0


def test_changedetect_flags_a_large_departure() -> None:
    baseline = compute_baseline(
        "test", "tile", "stat",
        [5.0, 5.2, 4.8, 5.1, 4.9, 5.0, 5.3, 4.7, 5.0, 5.1, 4.9, 5.2, 5.0, 4.8],
    )
    signal = classify(15.0, baseline)
    assert signal.outside_band
    assert signal.classification == "escalation"


def test_lake_series_covers_2016_to_now() -> None:
    series = build_series(PUREPU_LON, PUREPU_LAT)
    assert len(series) > 30
    years = {obs.acquired.year for obs in series}
    assert min(years) <= 2017
    assert max(years) >= 2025


def test_purepu_formation_window_is_cloud_obscured_and_logged() -> None:
    series = build_series(PUREPU_LON, PUREPU_LAT)
    july_2023 = [obs for obs in series if obs.acquired.year == 2023 and obs.acquired.month == 7]
    assert july_2023
    assert all(obs.obscured for obs in july_2023)
    assert all(obs.cloud_fraction > 0.9 for obs in july_2023)


def test_cloud_gap_log_is_non_empty() -> None:
    series = build_series(PUREPU_LON, PUREPU_LAT)
    gaps = cloud_gaps(series)
    assert len(gaps) > 5
    assert all(gap.span_days >= 20 for gap in gaps)
