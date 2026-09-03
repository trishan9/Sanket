from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import Window

from core.config import paths
from core.errors import TerrainError

DEM_DIRECTORY = paths.bronze / "hma_dem"
NODATA = -9999.0


@dataclass(frozen=True)
class DemWindow:
    elevation: np.ndarray
    transform: rasterio.Affine
    crs: str
    pixel_area_m2: float
    row_offset: int
    col_offset: int
    source: Path

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.elevation)


@lru_cache(maxsize=1)
def dem_tiles(directory: Path | None = None) -> tuple[Path, ...]:
    root = directory or DEM_DIRECTORY
    tiles = tuple(sorted(root.glob("*.tif")))
    if not tiles:
        raise TerrainError(f"no DEM tiles under {root}")
    return tiles


def _to_dem_crs(path: Path, lon: float, lat: float) -> tuple[float, float]:
    with rasterio.open(path) as dataset:
        transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
        return transformer.transform(lon, lat)


def tile_for(lon: float, lat: float, directory: Path | None = None) -> Path:
    for path in dem_tiles(directory):
        x, y = _to_dem_crs(path, lon, lat)
        with rasterio.open(path) as dataset:
            bounds = dataset.bounds
            if bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top:
                return path
    raise TerrainError(f"point ({lon}, {lat}) is outside every DEM tile")


def read_window(
    lon: float, lat: float, radius_m: float = 4000.0, directory: Path | None = None
) -> DemWindow:
    path = tile_for(lon, lat, directory)
    with rasterio.open(path) as dataset:
        x, y = _to_dem_crs(path, lon, lat)
        row, col = dataset.index(x, y)
        pixels = int(radius_m / dataset.res[0])
        row_off = max(0, row - pixels)
        col_off = max(0, col - pixels)
        height = min(dataset.height - row_off, pixels * 2)
        width = min(dataset.width - col_off, pixels * 2)
        window = Window(col_off, row_off, width, height)
        data = dataset.read(1, window=window).astype(np.float32)
        data[data == NODATA] = np.nan
        return DemWindow(
            elevation=data,
            transform=dataset.window_transform(window),
            crs=str(dataset.crs),
            pixel_area_m2=float(dataset.res[0] * dataset.res[1]),
            row_offset=row_off,
            col_offset=col_off,
            source=path,
        )


def elevation_at(lon: float, lat: float, directory: Path | None = None) -> float:
    path = tile_for(lon, lat, directory)
    x, y = _to_dem_crs(path, lon, lat)
    with rasterio.open(path) as dataset:
        value = float(next(iter(dataset.sample([(x, y)])))[0])
    if value == NODATA or not np.isfinite(value):
        raise TerrainError(f"no elevation at ({lon}, {lat})")
    return value


def window_index(window: DemWindow, lon: float, lat: float) -> tuple[int, int]:
    transformer = Transformer.from_crs("EPSG:4326", window.crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    inverse = ~window.transform
    col, row = inverse @ (x, y)
    return int(row), int(col)
