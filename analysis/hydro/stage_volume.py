from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy import ndimage

from analysis.hydro.dem import DemWindow, read_window, window_index
from core.errors import NoImpoundmentError, TerrainError
from core.provenance import Evidence, Provenance, Uncertainty

DEM_SOURCE = "NASA HMA 8 m DEM (HMA_DEM8m_MOS)"
DEM_VINTAGE = date(2017, 7, 16)
DEM_METHOD = (
    "barrier-constrained hypsometric fill: a dam of stated crest height is imposed across "
    "the channel at the blockage cell and water is impounded upstream, 8-connected, "
    "terminated at spill or domain edge"
)


@dataclass(frozen=True)
class StagePoint:
    level_m: float
    depth_m: float
    area_m2: float
    volume_m3: float


@dataclass(frozen=True)
class StageVolumeCurve:
    points: tuple[StagePoint, ...]
    base_elevation_m: float
    spill_level_m: float | None
    spill_limited: bool
    window_truncated: bool
    void_fraction: float
    pixel_area_m2: float

    def at_volume(self, target_m3: float) -> StagePoint:
        if not self.points:
            raise NoImpoundmentError("empty stage-volume curve")
        for point in self.points:
            if point.volume_m3 >= target_m3:
                return point
        return self.points[-1]

    def at_level(self, level_m: float) -> StagePoint:
        if not self.points:
            raise NoImpoundmentError("empty stage-volume curve")
        return min(self.points, key=lambda p: abs(p.level_m - level_m))

    @property
    def max_volume_m3(self) -> float:
        return self.points[-1].volume_m3 if self.points else 0.0


def descent_vector(
    elevation: np.ndarray, row: int, col: int, reach: int = 6
) -> tuple[float, float]:
    window = elevation[row - reach : row + reach + 1, col - reach : col + reach + 1]
    if window.size == 0 or not np.isfinite(window).any():
        raise TerrainError("cannot establish channel direction at the blockage cell")
    filled = np.where(np.isfinite(window), window, np.inf)
    index = int(np.argmin(filled))
    local_row, local_col = divmod(index, filled.shape[1])
    dr = float(local_row - reach)
    dc = float(local_col - reach)
    norm = float(np.hypot(dr, dc))
    if norm == 0.0:
        raise TerrainError("blockage cell is a local minimum; no channel direction")
    return dr / norm, dc / norm


def build_barrier(
    shape: tuple[int, int],
    row: int,
    col: int,
    direction: tuple[float, float],
    half_width_px: int,
    thickness_px: int,
) -> np.ndarray:
    rows, cols = np.indices(shape)
    dr, dc = direction
    along = (rows - row) * dr + (cols - col) * dc
    across = (rows - row) * (-dc) + (cols - col) * dr
    return (np.abs(along) <= thickness_px) & (np.abs(across) <= half_width_px)


def _component_at(mask: np.ndarray, row: int, col: int) -> np.ndarray | None:
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if count == 0:
        return None
    target = int(labels[row, col])
    if target == 0:
        return None
    component: np.ndarray = labels == target
    return component


def _touches_edge(component: np.ndarray) -> bool:
    return bool(
        component[0, :].any()
        or component[-1, :].any()
        or component[:, 0].any()
        or component[:, -1].any()
    )


def dam_surface(
    window: DemWindow,
    row: int,
    col: int,
    dam_height_m: float,
    step_m: float,
    barrier_half_width_m: float,
    barrier_thickness_m: float,
    barrier_offset_m: float,
) -> np.ndarray:
    elevation = window.elevation
    base = float(elevation[row, col])
    pixel = float(np.sqrt(window.pixel_area_m2))
    direction = descent_vector(elevation, row, col)
    offset = int(barrier_offset_m / pixel)
    barrier = build_barrier(
        elevation.shape,
        int(round(row + direction[0] * offset)),
        int(round(col + direction[1] * offset)),
        direction,
        int(barrier_half_width_m / pixel),
        max(1, int(barrier_thickness_m / pixel)),
    )
    if barrier[row, col]:
        raise TerrainError("blockage cell lies inside the modelled barrier")
    return np.where(barrier, base + dam_height_m + step_m, elevation)


def _accumulate(
    window: DemWindow,
    dammed: np.ndarray,
    row: int,
    col: int,
    base: float,
    dam_height_m: float,
    step_m: float,
) -> tuple[list[StagePoint], float | None, bool]:
    elevation = window.elevation
    valid = np.isfinite(elevation)
    points: list[StagePoint] = []
    spill_level: float | None = None
    for rise in np.arange(step_m, dam_height_m + step_m, step_m):
        level = base + float(rise)
        component = _component_at(valid & (dammed <= level), row, col)
        if component is None:
            continue
        if _touches_edge(component):
            return points, spill_level, True
        depths = np.clip(level - elevation[component], 0.0, None)
        points.append(
            StagePoint(
                level,
                float(rise),
                float(component.sum() * window.pixel_area_m2),
                float(np.nansum(depths) * window.pixel_area_m2),
            )
        )
        spill_level = level
    return points, spill_level, False


def compute_curve(
    window: DemWindow,
    row: int,
    col: int,
    *,
    dam_height_m: float = 60.0,
    step_m: float = 1.0,
    barrier_half_width_m: float = 600.0,
    barrier_thickness_m: float = 40.0,
    barrier_offset_m: float = 64.0,
) -> StageVolumeCurve:
    base = float(window.elevation[row, col])
    if not np.isfinite(base):
        raise TerrainError("blockage cell falls in a DEM void")
    dammed = dam_surface(
        window,
        row,
        col,
        dam_height_m,
        step_m,
        barrier_half_width_m,
        barrier_thickness_m,
        barrier_offset_m,
    )
    points, spill_level, truncated = _accumulate(
        window, dammed, row, col, base, dam_height_m, step_m
    )
    return StageVolumeCurve(
        points=tuple(points),
        base_elevation_m=base,
        spill_level_m=spill_level,
        spill_limited=not truncated and bool(points),
        window_truncated=truncated,
        void_fraction=float(1.0 - np.isfinite(window.elevation).mean()),
        pixel_area_m2=window.pixel_area_m2,
    )


def stage_volume(
    lon: float,
    lat: float,
    *,
    as_of: date,
    radius_m: float = 3000.0,
    dam_height_m: float = 60.0,
) -> Evidence:
    window = read_window(lon, lat, radius_m=radius_m)
    row, col = window_index(window, lon, lat)
    curve = compute_curve(window, row, col, dam_height_m=dam_height_m)
    value = _curve_value(lon, lat, curve, dam_height_m)
    provenance = _curve_provenance(window, curve, as_of)
    return Evidence(value=value, provenance=provenance, claim_type="model_output")


def _curve_value(
    lon: float, lat: float, curve: StageVolumeCurve, dam_height_m: float
) -> dict[str, object]:
    top = curve.points[-1] if curve.points else None
    return {
        "lon": lon,
        "lat": lat,
        "base_elevation_m": round(curve.base_elevation_m, 1),
        "max_volume_m3": round(curve.max_volume_m3, 0),
        "max_volume_Mm3": round(curve.max_volume_m3 / 1e6, 3),
        "impounded_area_m2": round(top.area_m2, 0) if top else 0.0,
        "spill_level_m": round(curve.spill_level_m, 1) if curve.spill_level_m else None,
        "dam_height_m": dam_height_m,
        "window_truncated": curve.window_truncated,
        "curve": [
            {
                "level_m": round(p.level_m, 1),
                "depth_m": round(p.depth_m, 1),
                "area_m2": round(p.area_m2, 0),
                "volume_m3": round(p.volume_m3, 0),
            }
            for p in curve.points
        ],
    }


def _curve_provenance(window: DemWindow, curve: StageVolumeCurve, as_of: date) -> Provenance:
    return Provenance(
        source=DEM_SOURCE,
        method=DEM_METHOD,
        as_of_filter=as_of,
        dataset_vintage=DEM_VINTAGE.isoformat(),
        independence_group="hma_dem_terrain",
        license="public domain (NASA)",
        uncertainty=Uncertainty(
            pixel_area_m2=window.pixel_area_m2,
            relative_error=curve.void_fraction,
            note=f"DEM voids {curve.void_fraction:.1%} of window",
        ),
        caveats=(
            "the DEM predates the event; post-event routing is wrong in ways we cannot "
            "correct without new survey",
            "window-truncated curves understate capacity"
            if curve.window_truncated
            else "curve is spill-limited within the analysis window",
        ),
    )
