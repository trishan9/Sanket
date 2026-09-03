from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from scipy import ndimage

if not hasattr(np, "in1d"):
    np.__dict__["in1d"] = np.isin

from analysis.hydro.dem import tile_for
from core.errors import TerrainError

FLOW_ACCUMULATION_THRESHOLD_CELLS = 300


@dataclass(frozen=True)
class ConditionedCorridor:
    filled: np.ndarray
    flow_direction: np.ndarray
    flow_accumulation: np.ndarray
    channel_mask: np.ndarray
    transform: rasterio.Affine
    crs: str
    pixel_size_m: float
    row_offset: int
    col_offset: int
    source_tile: str

    def to_grid_rowcol(self, lon: float, lat: float) -> tuple[int, int]:
        transformer = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        inverse = ~self.transform
        col, row = inverse @ (x, y)
        return int(row), int(col)


def _bounds_in_dem_crs(
    corners_lonlat: list[tuple[float, float]], tile_path: str
) -> tuple[float, float, float, float]:
    with rasterio.open(tile_path) as dataset:
        transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
        xs, ys = zip(*(transformer.transform(lon, lat) for lon, lat in corners_lonlat), strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def _buffered_bounds(
    tile_path: str, bounds: tuple[float, float, float, float], buffer_m: float
) -> tuple[tuple[float, float, float, float], float]:
    left, bottom, right, top = bounds
    with rasterio.open(tile_path) as dataset:
        clip_left = max(left - buffer_m, dataset.bounds.left)
        clip_bottom = max(bottom - buffer_m, dataset.bounds.bottom)
        clip_right = min(right + buffer_m, dataset.bounds.right)
        clip_top = min(top + buffer_m, dataset.bounds.top)
        pixel_size = float(dataset.res[0])
    clipped_bounds = (clip_left, clip_bottom, clip_right, clip_top)
    return clipped_bounds, pixel_size


def _void_filled_array(
    tile_path: str, window_bounds: tuple[float, float, float, float]
) -> tuple[np.ndarray, rasterio.Affine, object]:
    with rasterio.open(tile_path) as dataset:
        window = dataset.window(*window_bounds)
        window = window.round_offsets().round_lengths()
        array = dataset.read(1, window=window).astype(np.float32)
        transform = dataset.window_transform(window)
        crs = dataset.crs
        nodata = dataset.nodata
    void = (array == nodata) | ~np.isfinite(array)
    if void.any() and not void.all():
        _, indices = ndimage.distance_transform_edt(void, return_indices=True)
        array = array[tuple(indices)]
    array = np.pad(array, 1, mode="constant", constant_values=np.float32(-9999.0))
    padded_transform = transform @ rasterio.Affine.translation(-1, -1)
    return array, padded_transform, crs


def condition_corridor(
    corner_points_lonlat: list[tuple[float, float]], *, buffer_m: float = 1500.0
) -> ConditionedCorridor:
    reference_lon, reference_lat = corner_points_lonlat[0]
    tile_path = str(tile_for(reference_lon, reference_lat))
    raw_bounds = _bounds_in_dem_crs(corner_points_lonlat, tile_path)
    window_bounds, pixel_size = _buffered_bounds(tile_path, raw_bounds, buffer_m)

    array, transform, crs = _void_filled_array(tile_path, window_bounds)
    viewfinder = ViewFinder(
        affine=transform, shape=array.shape, crs=crs, nodata=np.float32(-9999.0)
    )
    dem = Raster(array, viewfinder=viewfinder)
    grid = Grid.from_raster(dem)
    row_offset, col_offset = 0, 0

    filled_flats = grid.fill_depressions(dem)
    inflated = grid.resolve_flats(filled_flats)
    flow_direction = grid.flowdir(inflated)
    flow_accumulation = grid.accumulation(flow_direction)

    channel_mask = np.asarray(flow_accumulation) >= FLOW_ACCUMULATION_THRESHOLD_CELLS
    if not channel_mask.any():
        raise TerrainError("no channel cells found above the accumulation threshold")

    dem_crs = str(crs)

    return ConditionedCorridor(
        filled=np.asarray(inflated),
        flow_direction=np.asarray(flow_direction),
        flow_accumulation=np.asarray(flow_accumulation),
        channel_mask=channel_mask,
        transform=transform,
        crs=dem_crs,
        pixel_size_m=pixel_size,
        row_offset=row_offset,
        col_offset=col_offset,
        source_tile=tile_path,
    )


def trace_downstream(
    corridor: ConditionedCorridor, start_lonlat: tuple[float, float], *, max_steps: int = 20000
) -> list[tuple[int, int]]:
    row, col = corridor.to_grid_rowcol(*start_lonlat)
    offsets = {
        64: (-1, 0),
        128: (-1, 1),
        1: (0, 1),
        2: (1, 1),
        4: (1, 0),
        8: (1, -1),
        16: (0, -1),
        32: (-1, -1),
    }
    path = [(row, col)]
    height, width = corridor.flow_direction.shape
    for _ in range(max_steps):
        if not (0 <= row < height and 0 <= col < width):
            break
        direction = int(corridor.flow_direction[row, col])
        if direction not in offsets:
            break
        d_row, d_col = offsets[direction]
        row, col = row + d_row, col + d_col
        path.append((row, col))
    return path


def nearest_channel_distance_m(
    corridor: ConditionedCorridor, point_lonlat: tuple[float, float]
) -> float:
    row, col = corridor.to_grid_rowcol(*point_lonlat)
    channel_rows, channel_cols = np.where(corridor.channel_mask)
    if len(channel_rows) == 0:
        raise TerrainError("no channel cells to measure distance against")
    distances = np.hypot(channel_rows - row, channel_cols - col) * corridor.pixel_size_m
    return float(distances.min())
