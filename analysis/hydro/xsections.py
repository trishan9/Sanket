from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import Transformer

from analysis.hydro.conditioning import ConditionedCorridor, trace_downstream
from core.corridor import Corridor
from core.errors import TerrainError

STAGE_STEP_M = 1.0
STAGE_MAX_M = 120.0
SECTION_HALF_WIDTH_M = 800.0
SAMPLE_STEP_M = 8.0
CHAINAGE_STEP_M = 200.0


@dataclass(frozen=True)
class ChannelSections:
    chainage_m: np.ndarray
    thalweg_m: np.ndarray
    stage_m: np.ndarray
    area_m2: np.ndarray
    width_m: np.ndarray
    x_m: np.ndarray
    y_m: np.ndarray
    crs: str


def _path_to_chainage(
    corridor: ConditionedCorridor, path: list[tuple[int, int]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = np.array([p[0] for p in path], dtype=np.float64)
    cols = np.array([p[1] for p in path], dtype=np.float64)
    xs = corridor.transform.c + cols * corridor.transform.a + rows * corridor.transform.b
    ys = corridor.transform.f + cols * corridor.transform.d + rows * corridor.transform.e
    steps = np.hypot(np.diff(xs), np.diff(ys))
    chainage = np.concatenate([[0.0], np.cumsum(steps)])
    return chainage, xs, ys


def _sample_elevation(corridor: ConditionedCorridor, row: float, col: float) -> float:
    height, width = corridor.filled.shape
    r, c = int(round(row)), int(round(col))
    if not (0 <= r < height and 0 <= c < width):
        return float("nan")
    value = float(corridor.filled[r, c])
    return value if np.isfinite(value) else float("nan")


def _perpendicular_profile(
    corridor: ConditionedCorridor, x0: float, y0: float, nx: float, ny: float, sign: float
) -> list[float]:
    profile = []
    envelope = -np.inf
    inverse = ~corridor.transform
    thalweg = _sample_elevation(corridor, *(inverse @ (x0, y0))[::-1])
    for distance in np.arange(0, SECTION_HALF_WIDTH_M + 1, SAMPLE_STEP_M):
        px, py = x0 + sign * nx * distance, y0 + sign * ny * distance
        col, row = inverse @ (px, py)
        z = _sample_elevation(corridor, row, col)
        if not np.isfinite(z):
            z = envelope if np.isfinite(envelope) else thalweg
        envelope = max(envelope, z)
        profile.append(envelope - thalweg if np.isfinite(thalweg) else float("nan"))
        if np.isfinite(thalweg) and envelope - thalweg > STAGE_MAX_M + 5:
            break
    return profile


def _hypsometry_at_station(depths: list[float]) -> tuple[np.ndarray, np.ndarray]:
    stage_axis = np.arange(0, STAGE_MAX_M + 1, STAGE_STEP_M)
    profile = np.array(depths)
    area = np.zeros(len(stage_axis))
    width = np.zeros(len(stage_axis))
    for j, stage in enumerate(stage_axis):
        wet = profile < stage
        width[j] = wet.sum() * SAMPLE_STEP_M
        area[j] = float(np.sum(np.clip(stage - profile[wet], 0, None))) * SAMPLE_STEP_M
    return area, width


def _station_direction(
    chainage: np.ndarray, xs: np.ndarray, ys: np.ndarray, chain_position: float
) -> tuple[float, float, float, float]:
    index = int(np.clip(np.searchsorted(chainage, chain_position), 5, len(chainage) - 6))
    x0, y0 = float(xs[index]), float(ys[index])
    dx, dy = xs[index + 5] - xs[index - 5], ys[index + 5] - ys[index - 5]
    length = float(np.hypot(dx, dy)) or 1.0
    return x0, y0, -dy / length, dx / length


def _fill_station_tables(
    corridor: ConditionedCorridor,
    stations: np.ndarray,
    chainage: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    stage_axis: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    thalweg = np.zeros(len(stations))
    station_x = np.zeros(len(stations))
    station_y = np.zeros(len(stations))
    area_table = np.zeros((len(stations), len(stage_axis)))
    width_table = np.zeros((len(stations), len(stage_axis)))
    for k, chain_position in enumerate(stations):
        x0, y0, nx, ny = _station_direction(chainage, xs, ys, chain_position)
        left = _perpendicular_profile(corridor, x0, y0, nx, ny, 1.0)
        right = _perpendicular_profile(corridor, x0, y0, nx, ny, -1.0)
        area_table[k], width_table[k] = _hypsometry_at_station(left + right)
        row, col = ~corridor.transform @ (x0, y0)
        thalweg[k] = _sample_elevation(corridor, col, row)
        station_x[k], station_y[k] = x0, y0
    return thalweg, station_x, station_y, area_table, width_table


def build_sections(
    corridor: ConditionedCorridor, start_lonlat: tuple[float, float]
) -> ChannelSections:
    path = trace_downstream(corridor, start_lonlat, max_steps=40000)
    if len(path) < 10:
        raise TerrainError("downstream trace too short to build cross-sections")
    chainage, xs, ys = _path_to_chainage(corridor, path)

    stations = np.arange(0.0, chainage[-1] - CHAINAGE_STEP_M, CHAINAGE_STEP_M)
    stage_axis = np.arange(0, STAGE_MAX_M + 1, STAGE_STEP_M)
    thalweg, station_x, station_y, area_table, width_table = _fill_station_tables(
        corridor, stations, chainage, xs, ys, stage_axis
    )

    valid = np.isfinite(thalweg)
    thalweg = np.interp(stations, stations[valid], thalweg[valid])
    thalweg = np.minimum.accumulate(thalweg)

    return ChannelSections(
        chainage_m=stations,
        thalweg_m=thalweg,
        stage_m=stage_axis,
        area_m2=area_table,
        width_m=width_table,
        x_m=station_x,
        y_m=station_y,
        crs=corridor.crs,
    )


def chainage_for_point(sections: ChannelSections, point_lonlat: tuple[float, float]) -> float:
    transformer = Transformer.from_crs("EPSG:4326", sections.crs, always_xy=True)
    x, y = transformer.transform(*point_lonlat)
    distances = np.hypot(sections.x_m - x, sections.y_m - y)
    return float(sections.chainage_m[int(np.argmin(distances))])


def chainages_for_corridor(corridor: Corridor, start_feature_id: str) -> dict[str, float]:
    from analysis.hydro.conditioning import condition_corridor

    conditioned = condition_corridor(
        [(corridor.bbox[0], corridor.bbox[1]), (corridor.bbox[2], corridor.bbox[3])]
    )
    feature = corridor.feature(start_feature_id)
    sections = build_sections(conditioned, feature.location)
    return {s.name: chainage_for_point(sections, s.location) for s in corridor.downstream_reach}
