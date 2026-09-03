from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry

from analysis.exposure.cells import strip_admin_fields
from analysis.hydro.dem import elevation_at
from core.config import paths
from core.errors import TerrainError

CANDIDATE_SEARCH_RADIUS_M = 3000.0
MINIMUM_ELEVATION_MARGIN_M = 10.0


@dataclass(frozen=True)
class AssemblyCandidate:
    name: str | None
    location: tuple[float, float]
    distance_m: float
    elevation_m: float | None
    above_peak_stage: bool


def _open_spaces() -> gpd.GeoDataFrame | None:
    path = paths.silver / "hot_flood_npl" / "Open Spaces (OSM), GeoJSON.parquet"
    if not path.exists():
        return None
    layer = strip_admin_fields(gpd.read_parquet(path))
    return layer[layer.geometry.notna()]


def _elevation_lonlat(point: BaseGeometry, crs: str) -> float | None:
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(point.centroid.x, point.centroid.y)
    try:
        return elevation_at(lon, lat)
    except TerrainError:
        return None


def candidates_near(
    settlement_point: BaseGeometry,
    *,
    peak_stage_elevation_m: float | None = None,
    radius_m: float = CANDIDATE_SEARCH_RADIUS_M,
) -> list[AssemblyCandidate]:
    layer = _open_spaces()
    if layer is None:
        return []
    buffer = settlement_point.buffer(radius_m)
    nearby = layer[layer.geometry.intersects(buffer)]
    results = []
    for _, row in nearby.iterrows():
        centroid = row.geometry.centroid
        elevation = _elevation_lonlat(row.geometry, str(layer.crs))
        above = (
            elevation is not None
            and peak_stage_elevation_m is not None
            and elevation > peak_stage_elevation_m + MINIMUM_ELEVATION_MARGIN_M
        )
        results.append(
            AssemblyCandidate(
                name=row.get("name"),
                location=(centroid.x, centroid.y),
                distance_m=float(settlement_point.distance(centroid)),
                elevation_m=elevation,
                above_peak_stage=above,
            )
        )
    return sorted(results, key=lambda c: c.distance_m)


def best_candidate(candidates: list[AssemblyCandidate]) -> AssemblyCandidate | None:
    safe = [c for c in candidates if c.above_peak_stage]
    ranked = safe or candidates
    return ranked[0] if ranked else None
