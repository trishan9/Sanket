from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import numpy as np

BreachMode = Literal["partial", "full", "progressive"]

SAMPLE_STEP_S = 5.0


def triangular_hydrograph(volume_m3: float, duration_s: float) -> Callable[[float], float]:
    peak = 2 * volume_m3 / duration_s
    rise = duration_s / 6

    def inflow(t: float) -> float:
        if t < 0 or t >= duration_s:
            return 0.0
        if t < rise:
            return peak * (t / rise)
        return peak * (1 - (t - rise) / (duration_s - rise))

    return inflow


def _gamma_hydrograph(
    volume_m3: float, peak_time_s: float, shape_k: float
) -> Callable[[float], float]:
    time_axis = np.arange(0, 4 * peak_time_s * shape_k + 3600, SAMPLE_STEP_S)
    ratio = time_axis / peak_time_s
    raw = np.where(ratio > 0, (ratio * np.exp(1 - ratio)) ** shape_k, 0.0)
    scale = volume_m3 / np.trapezoid(raw, time_axis)

    def inflow(t: float) -> float:
        if t <= 0:
            return 0.0
        r = t / peak_time_s
        return float(scale * (r * np.exp(1 - min(r, 50))) ** shape_k)

    return inflow


def breach_hydrograph(
    volume_m3: float, duration_s: float, mode: BreachMode
) -> Callable[[float], float]:
    if mode == "partial":
        return triangular_hydrograph(volume_m3, duration_s)
    if mode == "full":
        return _gamma_hydrograph(volume_m3, peak_time_s=180.0, shape_k=1.2)
    if mode == "progressive":
        return _gamma_hydrograph(volume_m3, peak_time_s=1200.0, shape_k=3.0)
    raise ValueError(f"unknown breach mode: {mode}")


def peak_inflow(hydrograph: Callable[[float], float], duration_s: float) -> float:
    samples = np.arange(0, 3 * duration_s, 10.0)
    return max(hydrograph(float(t)) for t in samples)
