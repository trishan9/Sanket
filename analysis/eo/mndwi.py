from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from skimage.filters import threshold_otsu

from core.config import paths
from core.errors import DetectionError

SCL_CLOUD_CLASSES = (0, 1, 3, 8, 9, 10)
LITERATURE_WATER_THRESHOLD = 0.0
MNDWI_SEARCH_LOW = -0.1
MNDWI_SEARCH_HIGH = 0.5
MIN_CANDIDATES_FOR_OTSU = 200
SCENE_DATE = re.compile(r"MSIL2A_(\d{8})T")


@dataclass(frozen=True)
class MndwiObservation:
    acquired: datetime
    scene_id: str
    mndwi: np.ndarray
    water_mask: np.ndarray
    clear_mask: np.ndarray
    cloud_fraction: float
    threshold: float
    transform: rasterio.Affine
    crs: str
    pixel_area_m2: float


def _water_threshold(mndwi: np.ndarray, candidate_mask: np.ndarray) -> float:
    candidates = mndwi[candidate_mask & (mndwi > MNDWI_SEARCH_LOW) & (mndwi < MNDWI_SEARCH_HIGH)]
    if candidates.size < MIN_CANDIDATES_FOR_OTSU or np.ptp(candidates) < 1e-6:
        return LITERATURE_WATER_THRESHOLD
    return float(threshold_otsu(candidates))


def _acquired(scene_id: str) -> datetime:
    match = SCENE_DATE.search(scene_id)
    if match is None:
        raise DetectionError(f"cannot parse date from scene id {scene_id}")
    return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=UTC)


def list_scene_ids() -> list[str]:
    root = paths.bronze / "sentinel_2_l2a"
    ids = {f.name.rsplit("_", 1)[0] for f in root.glob("*_B03.tif")}
    return sorted(ids)


def _resample_to(source_path: Path, reference_path: Path) -> np.ndarray:
    with rasterio.open(reference_path) as reference:
        target_shape = (reference.height, reference.width)
        target_transform = reference.transform
        target_crs = reference.crs
    with rasterio.open(source_path) as source:
        destination = np.zeros(target_shape, dtype=np.float32)
        reproject(
            source=rasterio.band(source, 1),
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=Resampling.average,
        )
    return destination


def compute_mndwi(scene_id: str) -> MndwiObservation:
    root = paths.bronze / "sentinel_2_l2a"
    green_path = root / f"{scene_id}_B03.tif"
    swir_path = root / f"{scene_id}_B11.tif"
    scl_path = root / f"{scene_id}_SCL.tif"
    if not (green_path.exists() and swir_path.exists() and scl_path.exists()):
        raise DetectionError(f"missing bands for scene {scene_id}")

    green = _resample_to(green_path, swir_path)
    with rasterio.open(swir_path) as dataset:
        swir = dataset.read(1).astype(np.float32)
        transform = dataset.transform
        crs = str(dataset.crs)
        pixel_area = float(dataset.res[0] * dataset.res[1])
    with rasterio.open(scl_path) as dataset:
        scl = dataset.read(1)

    clear = ~np.isin(scl, SCL_CLOUD_CLASSES)
    cloud_fraction = float(1.0 - clear.mean())

    denominator = green + swir
    mndwi = np.where(
        denominator > 0, (green - swir) / np.where(denominator == 0, 1, denominator), 0.0
    )

    threshold = _water_threshold(mndwi, clear & (denominator > 0))
    water = (mndwi > threshold) & clear

    return MndwiObservation(
        acquired=_acquired(scene_id),
        scene_id=scene_id,
        mndwi=mndwi,
        water_mask=water,
        clear_mask=clear,
        cloud_fraction=cloud_fraction,
        threshold=threshold,
        transform=transform,
        crs=crs,
        pixel_area_m2=pixel_area,
    )


def water_area_km2(observation: MndwiObservation) -> float:
    return float(observation.water_mask.sum() * observation.pixel_area_m2 / 1e6)
