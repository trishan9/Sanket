from __future__ import annotations

import time

from analysis.hydro.breach import breach_hydrograph
from analysis.hydro.conditioning import condition_corridor, nearest_channel_distance_m
from analysis.hydro.route1d import route
from analysis.hydro.scenarios import build_grid, grid_directory
from analysis.hydro.xsections import build_sections
from core.corridor import load_all_corridors

CORNERS = [(85.10, 27.90), (85.45, 28.40)]


def test_channel_network_matches_real_settlements() -> None:
    corridor = load_all_corridors()["bhotekoshi"]
    conditioned = condition_corridor(CORNERS)
    for settlement in corridor.downstream_reach:
        distance = nearest_channel_distance_m(conditioned, settlement.location)
        assert distance < 300, f"{settlement.name} is {distance:.0f} m from the channel"


def test_route1d_runs_under_ten_seconds_on_cpu() -> None:
    corridor = load_all_corridors()["bhotekoshi"]
    conditioned = condition_corridor(CORNERS)
    feature = conditioned and corridor.feature("lhende_barrier")
    sections = build_sections(conditioned, feature.location)
    hydrograph = breach_hydrograph(2.0e6, 1800, "full")
    start = time.time()
    route(sections, hydrograph, duration_s=3 * 3600, observation_chainage_m=[400.0, 15200.0])
    assert time.time() - start < 10.0


def test_scenario_grid_has_the_full_56_combinations() -> None:
    grid = build_grid()
    assert len(grid) == 56
    volumes = {key.volume_mm3 for key in grid}
    durations = {key.duration_s for key in grid}
    assert len(volumes) == 8
    assert len(durations) == 7


def test_scenario_grid_files_exist_on_disk() -> None:
    grid = build_grid()
    directory = grid_directory()
    missing = [key.slug for key in grid if not (directory / f"{key.slug}.npz").exists()]
    assert not missing, f"missing scenario files: {missing}"


def test_scenario_cog_loads_under_two_hundred_ms() -> None:
    import rasterio

    cog_path = grid_directory() / "reference_v1.0_d30_full_peak_rise.tif"
    assert cog_path.exists()
    start = time.time()
    with rasterio.open(cog_path) as dataset:
        bounds = dataset.bounds
        window = dataset.window(
            bounds.left, bounds.bottom, bounds.left + 2000, bounds.bottom + 2000
        )
        dataset.read(1, window=window)
    assert (time.time() - start) < 0.2
