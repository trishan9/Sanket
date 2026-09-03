from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

from analysis.hydro.scenarios import ScenarioKey, grid_directory, load_scenario
from analysis.hydro.xsections import ChannelSections
from core.errors import RoutingError

DEFAULT_RESOLUTION_M = 30.0
STAGE_FLOOR_M = 0.5


def _grid_extent(
    sections: ChannelSections, resolution_m: float, buffer_m: float
) -> tuple[rasterio.Affine, int, int]:
    min_x, max_x = sections.x_m.min() - buffer_m, sections.x_m.max() + buffer_m
    min_y, max_y = sections.y_m.min() - buffer_m, sections.y_m.max() + buffer_m
    width = int((max_x - min_x) / resolution_m)
    height = int((max_y - min_y) / resolution_m)
    return from_origin(min_x, max_y, resolution_m, resolution_m), width, height


def _footprint_width(sections: ChannelSections, peak_rise_at_station: np.ndarray) -> np.ndarray:
    footprint = np.zeros(len(sections.chainage_m))
    for k in range(len(sections.chainage_m)):
        target_stage = peak_rise_at_station[k] + STAGE_FLOOR_M
        footprint[k] = np.interp(target_stage, sections.stage_m, sections.width_m[k])
    return footprint


def rasterize_peak_rise(
    sections: ChannelSections,
    chainage_m: np.ndarray,
    peak_rise_m: np.ndarray,
    *,
    resolution_m: float = DEFAULT_RESOLUTION_M,
    buffer_m: float = 500.0,
) -> tuple[np.ndarray, rasterio.Affine]:
    transform, width, height = _grid_extent(sections, resolution_m, buffer_m)
    peak_at_station = np.interp(sections.chainage_m, chainage_m, peak_rise_m)
    footprint = _footprint_width(sections, peak_at_station)
    raster = np.zeros((height, width), dtype=np.float32)
    inverse = ~transform
    for k in range(len(sections.chainage_m)):
        col, row = inverse @ (sections.x_m[k], sections.y_m[k])
        half_px = max(1, int(footprint[k] / 2 / resolution_m))
        r, c = int(row), int(col)
        r0, r1 = max(0, r - half_px), min(height, r + half_px + 1)
        c0, c1 = max(0, c - half_px), min(width, c + half_px + 1)
        raster[r0:r1, c0:c1] = np.maximum(raster[r0:r1, c0:c1], peak_at_station[k])
    return raster, transform


def write_cog(raster: np.ndarray, transform: rasterio.Affine, crs: str, target: Path) -> Path:
    scratch = target.with_suffix(".raw.tif")
    with rasterio.open(
        scratch,
        "w",
        driver="GTiff",
        height=raster.shape[0],
        width=raster.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=0.0,
    ) as dataset:
        dataset.write(raster, 1)
    cog_translate(str(scratch), str(target), cog_profiles.get("deflate"), quiet=True)
    scratch.unlink()
    return target


def rasterize_scenario(
    sections: ChannelSections,
    key: ScenarioKey,
    crs: str,
    *,
    resolution_m: float = DEFAULT_RESOLUTION_M,
) -> Path:
    data = load_scenario(key.slug)
    if "chainage_m" not in data:
        raise RoutingError(f"scenario {key.slug} has no saved chainage data")
    raster, transform = rasterize_peak_rise(
        sections, data["chainage_m"], data["peak_rise_m"], resolution_m=resolution_m
    )
    target = grid_directory() / f"{key.slug}_peak_rise.tif"
    return write_cog(raster, transform, crs, target)
