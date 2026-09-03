from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio

from core.config import paths
from core.errors import DetectionError

OPEN_WATER = 1
PARTIAL_WATER = 2
NODATA_VALUES = (250, 251, 252, 253, 254, 255)
GRANULE_DATE = re.compile(r"_(\d{8})T\d{6}Z")


@dataclass(frozen=True)
class WaterObservation:
    acquired: datetime
    water_mask: np.ndarray
    valid_mask: np.ndarray
    transform: rasterio.Affine
    crs: str
    pixel_area_m2: float
    source_path: Path


def acquired_from_name(name: str) -> datetime:
    match = GRANULE_DATE.search(name)
    if match is None:
        raise DetectionError(f"cannot parse acquisition date from {name}")
    return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=UTC)


def list_wtr_files(tile: str | None = None) -> list[Path]:
    root = paths.bronze / "opera_l3_dswx_s1_v1"
    pattern = "*_WTR.tif"
    files = sorted(root.glob(pattern))
    if tile is not None:
        files = [f for f in files if tile in f.name]
    return files


def read_observation(path: Path, *, include_partial: bool = True) -> WaterObservation:
    with rasterio.open(path) as dataset:
        raw = dataset.read(1)
        transform = dataset.transform
        crs = str(dataset.crs)
        pixel_area = float(dataset.res[0] * dataset.res[1])
    valid = ~np.isin(raw, NODATA_VALUES)
    classes = (OPEN_WATER, PARTIAL_WATER) if include_partial else (OPEN_WATER,)
    water = np.isin(raw, classes) & valid
    return WaterObservation(
        acquired=acquired_from_name(path.name),
        water_mask=water,
        valid_mask=valid,
        transform=transform,
        crs=crs,
        pixel_area_m2=pixel_area,
        source_path=path,
    )


def water_area_km2(observation: WaterObservation) -> float:
    return float(observation.water_mask.sum() * observation.pixel_area_m2 / 1e6)


def observations_for_tile(tile: str) -> list[WaterObservation]:
    return sorted(
        (read_observation(path) for path in list_wtr_files(tile)),
        key=lambda obs: obs.acquired,
    )
