from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from shapely.geometry.base import BaseGeometry

from core.config import paths

ADMIN_FIELDS = tuple(f"adm{i}_{suffix}" for i in range(5) for suffix in ("pcode", "name"))


@dataclass(frozen=True)
class ExposureCount:
    population: float
    buildings: int
    bridges: int
    settlements: tuple[str, ...]
    area_km2: float


def strip_admin_fields(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    columns = [c for c in frame.columns if c not in ADMIN_FIELDS]
    return frame[columns]


def population_within(geometry: BaseGeometry, worldpop_path: Path | None = None) -> float:
    path = worldpop_path or (paths.silver / "worldpop" / "npl_ppp_2020_constrained.tif")
    if not path.exists():
        return 0.0
    with rasterio.open(path) as dataset:
        try:
            clipped, _ = rasterio_mask(dataset, [geometry], crop=True, nodata=0.0)
        except ValueError:
            return 0.0
    values = clipped[0]
    return float(np.where(np.isfinite(values) & (values > 0), values, 0.0).sum())


def _load_layer(name: str) -> gpd.GeoDataFrame | None:
    path = paths.silver / "hot_flood_npl" / f"{name}.parquet"
    if not path.exists():
        return None
    return strip_admin_fields(gpd.read_parquet(path))


def buildings_within(geometry: BaseGeometry) -> int:
    layer = _load_layer("Residential Areas (OSM), GeoJSON")
    if layer is None:
        return 0
    return int(layer.geometry.intersects(geometry).sum())


def bridges_within(geometry: BaseGeometry) -> int:
    layer = _load_layer("Bridges (OSM), GeoJSON")
    if layer is None:
        return 0
    return int(layer.geometry.intersects(geometry).sum())


def settlement_names_within(geometry: BaseGeometry) -> tuple[str, ...]:
    layer = _load_layer("Settlement Names (OSM), GeoJSON")
    if layer is None or "name" not in layer.columns:
        return ()
    hits = layer[layer.geometry.intersects(geometry)]
    return tuple(sorted({str(n) for n in hits["name"].dropna()}))


def exposure_at(geometry: BaseGeometry) -> ExposureCount:
    return ExposureCount(
        population=population_within(geometry),
        buildings=buildings_within(geometry),
        bridges=bridges_within(geometry),
        settlements=settlement_names_within(geometry),
        area_km2=float(geometry.area / 1e6),
    )
