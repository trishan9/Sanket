from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analysis.hydro.breach import BreachMode, breach_hydrograph
from analysis.hydro.route1d import RouteResult, route
from analysis.hydro.xsections import ChannelSections
from core.config import paths, settings

DURATION_SIMULATED_S = 3 * 3600.0
BREACH_MODES: tuple[BreachMode, ...] = ("partial", "full", "progressive")


@dataclass(frozen=True)
class ScenarioKey:
    volume_mm3: float
    duration_s: float
    mode: BreachMode

    @property
    def slug(self) -> str:
        return f"v{self.volume_mm3:.1f}_d{self.duration_s / 60:.0f}_{self.mode}"


@dataclass(frozen=True)
class ScenarioResult:
    key: ScenarioKey
    arrival_time_s: dict[float, float | None]
    peak_rise_m: dict[float, float]
    compute_seconds: float


def run_scenario(
    sections: ChannelSections,
    key: ScenarioKey,
    observation_chainage_m: list[float],
    *,
    inject_chainage_m: float = 0.0,
) -> ScenarioResult:
    hydrograph = breach_hydrograph(key.volume_mm3 * 1e6, key.duration_s, key.mode)
    start = time.time()
    result: RouteResult = route(
        sections,
        hydrograph,
        DURATION_SIMULATED_S,
        observation_chainage_m,
        inject_chainage_m=inject_chainage_m,
        rise_threshold_m=0.15,
    )
    elapsed = time.time() - start
    peak_rise = {
        chainage: float(series.max() - series[0])
        for chainage, series in result.stage_at_chainage.items()
    }
    return ScenarioResult(key, result.arrival_time_s, peak_rise, elapsed)


def build_grid(
    volumes_mm3: tuple[float, ...] = settings.scenario_volumes_mm3,
    breach_minutes: tuple[int, ...] = settings.scenario_breach_minutes,
    mode: BreachMode = "full",
) -> list[ScenarioKey]:
    return [
        ScenarioKey(volume, minutes * 60.0, mode)
        for volume in volumes_mm3
        for minutes in breach_minutes
    ]


def grid_directory() -> Path:
    target = paths.dist / "scenario_grid"
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_scenario(result: ScenarioResult) -> Path:
    target = grid_directory() / f"{result.key.slug}.npz"
    chainages = sorted(result.arrival_time_s)
    np.savez_compressed(
        target,
        volume_mm3=result.key.volume_mm3,
        duration_s=result.key.duration_s,
        mode=result.key.mode,
        chainage_m=np.array(chainages),
        arrival_time_s=np.array(
            [
                result.arrival_time_s[c] if result.arrival_time_s[c] is not None else np.nan
                for c in chainages
            ]
        ),
        peak_rise_m=np.array([result.peak_rise_m[c] for c in chainages]),
        compute_seconds=result.compute_seconds,
    )
    return target


def load_scenario(slug: str) -> dict[str, np.ndarray]:
    target = grid_directory() / f"{slug}.npz"
    with np.load(target, allow_pickle=True) as data:
        return dict(data)
