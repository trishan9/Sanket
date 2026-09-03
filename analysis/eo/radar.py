from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

from core.config import paths
from core.errors import DetectionError

BACKSCATTER_CEILING = 0.01
SCENE_DATE = re.compile(r"_(\d{8})T\d{6}_")
BoundsM = tuple[float, float, float, float]


@dataclass(frozen=True)
class RadarWaterObservation:
    acquired: datetime
    water_mask: np.ndarray
    valid_mask: np.ndarray
    transform: rasterio.Affine
    crs: str
    pixel_area_m2: float
    threshold: float
    source_path: Path


def _acquired(name: str) -> datetime:
    match = SCENE_DATE.search(name)
    if match is None:
        raise DetectionError(f"cannot parse date from {name}")
    return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=UTC)


def list_vv_files() -> list[Path]:
    root = paths.bronze / "sentinel_1_rtc"
    return sorted(root.glob("*_vv.tif"))


def detect_water(
    path: Path, *, ceiling: float = BACKSCATTER_CEILING, window_bounds_m: BoundsM | None = None
) -> RadarWaterObservation:
    with rasterio.open(path) as dataset:
        window = from_bounds(*window_bounds_m, dataset.transform) if window_bounds_m else None
        raw = dataset.read(1, window=window)
        transform = dataset.window_transform(window) if window else dataset.transform
        crs = str(dataset.crs)
        pixel_area = float(dataset.res[0] * dataset.res[1])
    valid = np.isfinite(raw) & (raw > 0)
    water = valid & (raw < ceiling)
    return RadarWaterObservation(
        acquired=_acquired(path.name),
        water_mask=water,
        valid_mask=valid,
        transform=transform,
        crs=crs,
        pixel_area_m2=pixel_area,
        threshold=ceiling,
        source_path=path,
    )


def water_area_km2(observation: RadarWaterObservation) -> float:
    return float(observation.water_mask.sum() * observation.pixel_area_m2 / 1e6)
