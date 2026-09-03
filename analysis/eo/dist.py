from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio

from analysis.eo.dswx import acquired_from_name
from core.config import paths

NO_DISTURBANCE = 0
CONFIRMED_CLASSES = (3, 6, 7, 8)
PROVISIONAL_CLASSES = (1, 2, 4, 5)
NODATA = 255


@dataclass(frozen=True)
class DisturbanceObservation:
    acquired: datetime
    confirmed_mask: np.ndarray
    provisional_mask: np.ndarray
    valid_mask: np.ndarray
    transform: rasterio.Affine
    crs: str
    pixel_area_m2: float
    source_path: Path


def list_status_files(tile: str | None = None) -> list[Path]:
    root = paths.bronze / "opera_l3_dist_alert_hls_v1"
    files = sorted(root.glob("*_VEG-DIST-STATUS.tif"))
    if tile is not None:
        files = [f for f in files if tile in f.name]
    return files


def read_observation(path: Path) -> DisturbanceObservation:
    with rasterio.open(path) as dataset:
        raw = dataset.read(1)
        transform = dataset.transform
        crs = str(dataset.crs)
        pixel_area = float(dataset.res[0] * dataset.res[1])
    valid = raw != NODATA
    return DisturbanceObservation(
        acquired=acquired_from_name(path.name),
        confirmed_mask=np.isin(raw, CONFIRMED_CLASSES) & valid,
        provisional_mask=np.isin(raw, PROVISIONAL_CLASSES) & valid,
        valid_mask=valid,
        transform=transform,
        crs=crs,
        pixel_area_m2=pixel_area,
        source_path=path,
    )


def disturbance_area_km2(
    observation: DisturbanceObservation, *, confirmed_only: bool = True
) -> float:
    mask = (
        observation.confirmed_mask
        if confirmed_only
        else (observation.confirmed_mask | observation.provisional_mask)
    )
    return float(mask.sum() * observation.pixel_area_m2 / 1e6)


def observations_for_tile(tile: str) -> list[DisturbanceObservation]:
    return sorted(
        (read_observation(path) for path in list_status_files(tile)),
        key=lambda obs: obs.acquired,
    )
