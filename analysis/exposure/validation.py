from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize

from core.config import paths
from core.errors import RegistryError


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def iou(self) -> float:
        union = self.true_positive + self.false_positive + self.false_negative
        return self.true_positive / union if union else 0.0

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


def load_cems_events(root: Path | None = None) -> gpd.GeoDataFrame:
    base = root or (paths.bronze / "manual" / "cems" / "EMSR927_products")
    if not base.exists():
        raise RegistryError(f"CEMS activation not found under {base}")
    shapefiles = sorted(base.glob("*/EMSR927_*observedEventA*.shp"))
    if not shapefiles:
        raise RegistryError(f"no observedEventA layers under {base}")
    frames = [gpd.read_file(path) for path in shapefiles]
    combined = gpd.pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(combined, crs=frames[0].crs)


def load_hdx_flood_extent() -> gpd.GeoDataFrame:
    path = paths.silver / "hot_flood_npl" / "Flood Extent, Observed 27 August 2026, GeoJSON.parquet"
    if not path.exists():
        raise RegistryError(f"HDX flood extent not found at {path}")
    return gpd.read_parquet(path)


def _rasterize_reference(
    reference: gpd.GeoDataFrame,
    model_transform: rasterio.Affine,
    model_crs: str,
    model_shape: tuple[int, int],
) -> np.ndarray:
    projected = reference.to_crs(model_crs)
    shapes = [(geom, 1) for geom in projected.geometry if geom is not None and not geom.is_empty]
    if not shapes:
        return np.zeros(model_shape, dtype=bool)
    burned = rasterize(shapes, out_shape=model_shape, transform=model_transform, fill=0)
    result: np.ndarray = burned.astype(bool)
    return result


def compare_to_reference(
    modelled_cog: Path,
    reference: gpd.GeoDataFrame,
    *,
    threshold_m: float = 0.1,
) -> ConfusionMatrix:
    with rasterio.open(modelled_cog) as dataset:
        modelled_raw = dataset.read(1)
        transform = dataset.transform
        crs = str(dataset.crs)
        shape = (dataset.height, dataset.width)
    modelled = modelled_raw > threshold_m
    reference_mask = _rasterize_reference(reference, transform, crs, shape)

    true_positive = int(np.logical_and(modelled, reference_mask).sum())
    false_positive = int(np.logical_and(modelled, ~reference_mask).sum())
    false_negative = int(np.logical_and(~modelled, reference_mask).sum())
    true_negative = int(np.logical_and(~modelled, ~reference_mask).sum())
    return ConfusionMatrix(true_positive, false_positive, false_negative, true_negative)
