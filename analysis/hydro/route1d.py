from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from analysis.hydro.xsections import ChannelSections
from core.errors import RoutingError

GRAVITY = 9.81
CFL_NUMBER = 0.3
MAX_DT_S = 2.0
MIN_AREA_M2 = 1e-3
MIN_WIDTH_M = 5.0
MANNING_UPPER = 0.10
MANNING_MID = 0.05
MANNING_LOWER = 0.04
UPPER_REACH_KM = 39.0
MID_REACH_KM = 72.0
RUN_DURATION_S = 6 * 3600.0
RECORD_EVERY_N_STEPS = 60


@dataclass(frozen=True)
class RouteResult:
    time_s: np.ndarray
    stage_at_chainage: dict[float, np.ndarray]
    peak_stage: np.ndarray
    chainage_m: np.ndarray
    arrival_time_s: dict[float, float | None]


def _manning_profile(chainage_m: np.ndarray) -> np.ndarray:
    km = chainage_m / 1000.0
    return np.where(
        km < UPPER_REACH_KM, MANNING_UPPER, np.where(km < MID_REACH_KM, MANNING_MID, MANNING_LOWER)
    )


def _stage_of_area(area_table: np.ndarray, stage_axis: np.ndarray, area: np.ndarray) -> np.ndarray:
    return np.array([np.interp(area[i], area_table[i], stage_axis) for i in range(len(area))])


def _width_of_stage(
    width_table: np.ndarray, stage_axis: np.ndarray, stage: np.ndarray
) -> np.ndarray:
    clipped = np.clip(stage, 0, stage_axis[-1])
    return np.array([np.interp(clipped[i], stage_axis, width_table[i]) for i in range(len(stage))])


def _rusanov_fluxes(
    area: np.ndarray, discharge: np.ndarray, velocity: np.ndarray, celerity: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    wave_speed = np.abs(velocity) + celerity
    local_max = np.maximum(wave_speed[:-1], wave_speed[1:])
    mass_flux = 0.5 * (discharge[:-1] + discharge[1:]) - 0.5 * local_max * (area[1:] - area[:-1])
    advective = discharge * velocity
    momentum_flux = 0.5 * (advective[:-1] + advective[1:]) - 0.5 * local_max * (
        discharge[1:] - discharge[:-1]
    )
    return mass_flux, momentum_flux


@dataclass
class RouterState:
    area: np.ndarray
    discharge: np.ndarray


def _hydraulic_terms(
    state: RouterState, sections: ChannelSections
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    stage = _stage_of_area(sections.area_m2, sections.stage_m, state.area)
    width = np.maximum(_width_of_stage(sections.width_m, sections.stage_m, stage), MIN_WIDTH_M)
    velocity = np.clip(state.discharge / state.area, -60, 60)
    return stage, width, velocity


def _apply_pressure_and_friction(
    state: RouterState,
    next_discharge: np.ndarray,
    sections: ChannelSections,
    stage: np.ndarray,
    width: np.ndarray,
    velocity: np.ndarray,
    manning: np.ndarray,
    dx: float,
    dt: float,
) -> np.ndarray:
    surface = sections.thalweg_m + stage
    gradient = np.zeros(len(state.area))
    gradient[1:-1] = (surface[2:] - surface[:-2]) / (2 * dx)
    next_discharge[1:-1] -= dt * GRAVITY * state.area[1:-1] * gradient[1:-1]

    hydraulic_radius = np.maximum(state.area / width, 0.05)
    friction = GRAVITY * manning**2 * np.abs(velocity) / hydraulic_radius ** (4.0 / 3.0)
    next_discharge[1:-1] /= 1 + dt * friction[1:-1]
    return next_discharge


def _advance(
    state: RouterState,
    sections: ChannelSections,
    manning: np.ndarray,
    dx: float,
    inject_index: int,
    inflow_m3s: float,
) -> tuple[RouterState, float]:
    stage, width, velocity = _hydraulic_terms(state, sections)
    depth = np.maximum(state.area / width, 0.02)
    celerity = np.sqrt(GRAVITY * depth)
    dt = float(
        min(CFL_NUMBER * dx / max(float((np.abs(velocity) + celerity).max()), 1.0), MAX_DT_S)
    )
    if not np.isfinite(dt) or dt <= 0:
        raise RoutingError("timestep collapsed to zero or non-finite")

    mass_flux, momentum_flux = _rusanov_fluxes(state.area, state.discharge, velocity, celerity)
    next_area = state.area.copy()
    next_discharge = state.discharge.copy()
    next_area[1:-1] -= dt / dx * (mass_flux[1:] - mass_flux[:-1])
    next_discharge[1:-1] -= dt / dx * (momentum_flux[1:] - momentum_flux[:-1])

    next_discharge = _apply_pressure_and_friction(
        state, next_discharge, sections, stage, width, velocity, manning, dx, dt
    )

    lo = max(inject_index - 1, 1)
    hi = min(inject_index + 2, len(next_area) - 1)
    next_area[lo:hi] += dt * inflow_m3s / ((hi - lo) * dx)
    next_area[0], next_discharge[0] = next_area[1], 0.0
    next_area[-1] = next_area[-2]

    return RouterState(np.maximum(next_area, MIN_AREA_M2), next_discharge), dt


def _initial_state(sections: ChannelSections, seed_stage_m: float = 0.5) -> RouterState:
    seed_area = np.array(
        [
            np.interp(seed_stage_m, sections.stage_m, sections.area_m2[i])
            for i in range(len(sections.chainage_m))
        ]
    )
    return RouterState(area=np.maximum(seed_area, MIN_AREA_M2), discharge=np.zeros_like(seed_area))


def _observation_indices(
    sections: ChannelSections, observation_chainage_m: list[float]
) -> dict[float, int]:
    return {
        chainage: int(np.searchsorted(sections.chainage_m, chainage))
        for chainage in observation_chainage_m
    }


@dataclass
class _RunLog:
    time_s: list[float]
    stage: dict[float, list[float]]
    arrival_time: dict[float, float | None]
    peak_stage: np.ndarray


def _record_step(
    log: _RunLog,
    t: float,
    stage: np.ndarray,
    baseline_stage: np.ndarray,
    observations: dict[float, int],
    rise_threshold_m: float,
) -> None:
    log.time_s.append(t)
    for chainage, index in observations.items():
        log.stage[chainage].append(float(stage[index]))
        rise = stage[index] - baseline_stage[index]
        if log.arrival_time[chainage] is None and rise > rise_threshold_m:
            log.arrival_time[chainage] = t


@dataclass(frozen=True)
class _RunConfig:
    sections: ChannelSections
    hydrograph: Callable[[float], float]
    duration_s: float
    manning: np.ndarray
    dx: float
    inject_index: int
    observations: dict[float, int]
    baseline_stage: np.ndarray
    rise_threshold_m: float


def _run_loop(config: _RunConfig, log: _RunLog) -> RouterState:
    sections = config.sections
    state = _initial_state(sections)
    t, step = 0.0, 0
    while t < config.duration_s:
        inflow = float(config.hydrograph(t))
        state, dt = _advance(
            state, sections, config.manning, config.dx, config.inject_index, inflow
        )
        stage = _stage_of_area(sections.area_m2, sections.stage_m, state.area)
        log.peak_stage = np.maximum(log.peak_stage, stage)
        if step % RECORD_EVERY_N_STEPS == 0:
            _record_step(
                log, t, stage, config.baseline_stage, config.observations, config.rise_threshold_m
            )
        t += dt
        step += 1
        if not np.isfinite(state.area).all() or not np.isfinite(state.discharge).all():
            raise RoutingError(f"solver diverged at t={t:.0f}s, step {step}")
    return state


def _setup_run(
    sections: ChannelSections,
    hydrograph: Callable[[float], float],
    duration_s: float,
    inject_chainage_m: float,
    observation_chainage_m: list[float],
    rise_threshold_m: float,
) -> tuple[_RunConfig, _RunLog]:
    dx = float(sections.chainage_m[1] - sections.chainage_m[0])
    manning = _manning_profile(sections.chainage_m)
    inject_index = int(np.searchsorted(sections.chainage_m, inject_chainage_m))
    observations = _observation_indices(sections, observation_chainage_m)
    baseline_stage = _stage_of_area(
        sections.area_m2, sections.stage_m, _initial_state(sections).area
    )
    log = _RunLog(
        time_s=[],
        stage={c: [] for c in observations},
        arrival_time=dict.fromkeys(observations),
        peak_stage=baseline_stage.copy(),
    )
    config = _RunConfig(
        sections,
        hydrograph,
        duration_s,
        manning,
        dx,
        inject_index,
        observations,
        baseline_stage,
        rise_threshold_m,
    )
    return config, log


def route(
    sections: ChannelSections,
    hydrograph: Callable[[float], float],
    duration_s: float,
    observation_chainage_m: list[float],
    *,
    inject_chainage_m: float = 0.0,
    rise_threshold_m: float = 0.5,
) -> RouteResult:
    if len(sections.chainage_m) < 10:
        raise RoutingError("channel too short to route")
    config, log = _setup_run(
        sections,
        hydrograph,
        duration_s,
        inject_chainage_m,
        observation_chainage_m,
        rise_threshold_m,
    )
    _run_loop(config, log)
    return RouteResult(
        time_s=np.array(log.time_s),
        stage_at_chainage={c: np.array(v) for c, v in log.stage.items()},
        peak_stage=log.peak_stage,
        chainage_m=sections.chainage_m,
        arrival_time_s=log.arrival_time,
    )
