from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from scipy import ndimage

from analysis.hydro.dem import dem_tiles
from core.config import paths
from core.errors import TerrainError

SCENARIO_DIRECTORY = paths.dist / "scenario_grid"
MIN_RENDERABLE_DEPTH_M = 0.05
SMALL_VOID_RADIUS_PX = 6.0
HILLSHADE_AZIMUTH_DEG = 315.0
HILLSHADE_ALTITUDE_DEG = 45.0


@dataclass(frozen=True)
class FloodRaster:
    depth_m: np.ndarray
    hillshade: np.ndarray
    dem_valid: np.ndarray
    transform: rasterio.Affine
    crs: str
    source: Path
    max_depth_m: float

    @property
    def wet_pixels(self) -> int:
        return int(np.isfinite(self.depth_m).sum())


def scenario_path(slug: str) -> Path:
    target = SCENARIO_DIRECTORY / f"{slug}_peak_rise.tif"
    if not target.exists():
        raise TerrainError(f"no rendered scenario raster for {slug} at {target}")
    return target


def hillshade(elevation: np.ndarray, pixel_size_m: float) -> np.ndarray:
    filled = np.where(np.isfinite(elevation), elevation, np.nanmedian(elevation))
    filled = ndimage.gaussian_filter(filled, sigma=1.4)
    dy, dx = np.gradient(filled, pixel_size_m)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    azimuth = np.radians(360.0 - HILLSHADE_AZIMUTH_DEG + 90.0)
    altitude = np.radians(HILLSHADE_ALTITUDE_DEG)
    shaded = np.sin(altitude) * np.cos(slope) + np.cos(altitude) * np.sin(slope) * np.cos(
        azimuth - aspect
    )
    lit: np.ndarray = np.clip(shaded, 0.0, 1.0)
    return lit


def _dem_on_grid(transform: rasterio.Affine, crs: str, shape: tuple[int, int]) -> np.ndarray:
    destination = np.full(shape, np.nan, dtype=np.float32)
    for tile in dem_tiles():
        with rasterio.open(tile) as dataset:
            patch = np.full(shape, np.nan, dtype=np.float32)
            reproject(
                source=rasterio.band(dataset, 1),
                destination=patch,
                dst_transform=transform,
                dst_crs=crs,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
        destination = np.where(np.isfinite(destination), destination, patch)
    return _fill_small_voids(destination)


def _fill_small_voids(elevation: np.ndarray) -> np.ndarray:
    void = ~np.isfinite(elevation)
    if not void.any():
        return elevation
    indices = ndimage.distance_transform_edt(void, return_distances=False, return_indices=True)
    filled = elevation[tuple(indices)]
    distance = ndimage.distance_transform_edt(void)
    result: np.ndarray = np.where(distance <= SMALL_VOID_RADIUS_PX, filled, np.nan)
    return result


def load_flood_raster(slug: str) -> FloodRaster:
    path = scenario_path(slug)
    with rasterio.open(path) as dataset:
        depth = dataset.read(1).astype(np.float32)
        transform = dataset.transform
        crs = str(dataset.crs)
        pixel_size = float(abs(dataset.res[0]))
    depth = np.where(depth > MIN_RENDERABLE_DEPTH_M, depth, np.nan)
    elevation = _dem_on_grid(transform, crs, depth.shape)
    return FloodRaster(
        depth_m=depth,
        hillshade=hillshade(elevation, pixel_size),
        dem_valid=np.isfinite(elevation),
        transform=transform,
        crs=crs,
        source=path,
        max_depth_m=float(np.nanmax(depth)) if np.isfinite(depth).any() else 0.0,
    )


def crop_to_flood(raster: FloodRaster, margin_px: int = 60) -> FloodRaster:
    wet = np.isfinite(raster.depth_m)
    if not wet.any():
        return raster
    rows, cols = np.where(wet)
    top = max(0, int(rows.min()) - margin_px)
    bottom = min(raster.depth_m.shape[0], int(rows.max()) + margin_px)
    left = max(0, int(cols.min()) - margin_px)
    right = min(raster.depth_m.shape[1], int(cols.max()) + margin_px)
    window = (slice(top, bottom), slice(left, right))
    return FloodRaster(
        depth_m=raster.depth_m[window],
        hillshade=raster.hillshade[window],
        dem_valid=raster.dem_valid[window],
        transform=raster.transform * rasterio.Affine.translation(left, top),
        crs=raster.crs,
        source=raster.source,
        max_depth_m=raster.max_depth_m,
    )


def lonlat_to_pixel(raster: FloodRaster, lon: float, lat: float) -> tuple[int, int]:
    transformer = Transformer.from_crs("EPSG:4326", raster.crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    col, row = ~raster.transform * (x, y)
    return int(round(row)), int(round(col))


def _depth_colour(normalised: np.ndarray) -> np.ndarray:
    stops = np.array(
        [
            [86, 180, 233],
            [39, 129, 214],
            [22, 82, 185],
            [124, 44, 168],
            [190, 30, 96],
        ],
        dtype=np.float32,
    )
    positions = np.linspace(0.0, 1.0, len(stops))
    channels = [np.interp(normalised, positions, stops[:, i]) for i in range(3)]
    stacked: np.ndarray = np.stack(channels, axis=-1)
    return stacked


def compose_rgb(raster: FloodRaster, widen_px: int = 0) -> np.ndarray:
    shade = raster.hillshade
    base = np.stack([shade * 150 + 40, shade * 158 + 46, shade * 152 + 52], axis=-1)
    base = np.where(raster.dem_valid[..., None], base, np.array([26, 28, 33], dtype=np.float32))
    depth = np.nan_to_num(raster.depth_m)
    if widen_px > 0:
        depth = ndimage.grey_dilation(depth, size=(widen_px, widen_px))
    wet = depth > MIN_RENDERABLE_DEPTH_M
    if not wet.any():
        dry: np.ndarray = np.clip(base, 0, 255).astype(np.uint8)
        return dry
    ceiling = max(raster.max_depth_m, MIN_RENDERABLE_DEPTH_M)
    colour = _depth_colour(np.clip(depth / ceiling, 0.0, 1.0))
    lit = colour * (0.62 + 0.38 * shade[..., None])
    halo = ndimage.binary_dilation(wet, iterations=max(1, widen_px // 2)) & ~wet
    blended = np.where(wet[..., None], lit, base)
    blended = np.where(halo[..., None], blended * 0.45 + np.array([12, 26, 48]), blended)
    return np.clip(blended, 0, 255).astype(np.uint8)
