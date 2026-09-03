from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pyproj import Transformer

from analysis.eo.mndwi import MndwiObservation, compute_mndwi, list_scene_ids
from core.errors import DetectionError

LOCAL_WINDOW_PX = 30
CLOUD_GAP_THRESHOLD = 0.5


@dataclass(frozen=True)
class LakeObservation:
    acquired: datetime
    scene_id: str
    area_km2: float
    cloud_fraction: float
    obscured: bool
    row: int
    col: int


@dataclass(frozen=True)
class CloudGap:
    start: datetime
    end: datetime
    span_days: float


def _local_area(observation: MndwiObservation, row: int, col: int, half: int) -> float:
    top, bottom = max(0, row - half), row + half
    left, right = max(0, col - half), col + half
    window = observation.water_mask[top:bottom, left:right]
    return float(window.sum() * observation.pixel_area_m2 / 1e6)


def observe_lake(scene_id: str, lon: float, lat: float) -> LakeObservation:
    observation = compute_mndwi(scene_id)
    transformer = Transformer.from_crs("EPSG:4326", observation.crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    inverse = ~observation.transform
    col, row = inverse @ (x, y)
    row, col = int(row), int(col)
    if not (
        0 <= row < observation.water_mask.shape[0] and 0 <= col < observation.water_mask.shape[1]
    ):
        raise DetectionError(f"({lon},{lat}) falls outside scene {scene_id}")
    local_clear = observation.clear_mask[
        max(0, row - LOCAL_WINDOW_PX) : row + LOCAL_WINDOW_PX,
        max(0, col - LOCAL_WINDOW_PX) : col + LOCAL_WINDOW_PX,
    ]
    obscured = bool(local_clear.mean() < CLOUD_GAP_THRESHOLD)
    area = 0.0 if obscured else _local_area(observation, row, col, LOCAL_WINDOW_PX)
    return LakeObservation(
        acquired=observation.acquired,
        scene_id=scene_id,
        area_km2=area,
        cloud_fraction=observation.cloud_fraction,
        obscured=obscured,
        row=row,
        col=col,
    )


def build_series(lon: float, lat: float) -> list[LakeObservation]:
    series = []
    for scene_id in list_scene_ids():
        try:
            series.append(observe_lake(scene_id, lon, lat))
        except DetectionError:
            continue
    return sorted(series, key=lambda obs: obs.acquired)


def cloud_gaps(series: list[LakeObservation], *, min_gap_days: float = 20.0) -> list[CloudGap]:
    usable = sorted(obs.acquired for obs in series if not obs.obscured)
    gaps = []
    for previous, current in zip(usable, usable[1:], strict=False):
        span = (current - previous).total_seconds() / 86400
        if span >= min_gap_days:
            gaps.append(CloudGap(start=previous, end=current, span_days=span))
    return gaps
