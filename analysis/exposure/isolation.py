from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

from analysis.exposure.cells import strip_admin_fields
from core.config import paths

BRIDGE_BUFFER_M = 50.0


@dataclass(frozen=True)
class BridgeDependency:
    bridge_name: str | None
    bridge_id: str
    within_inundation: bool


@dataclass(frozen=True)
class IsolationRisk:
    settlement: str
    total_bridges: int
    bridges_at_risk: int
    single_point_of_failure: bool
    dependent_bridges: tuple[BridgeDependency, ...]


def _load_bridges() -> gpd.GeoDataFrame | None:
    path = paths.silver / "hot_flood_npl" / "Bridges (OSM), GeoJSON.parquet"
    if not path.exists():
        return None
    return strip_admin_fields(gpd.read_parquet(path))


def bridges_near(settlement_point: BaseGeometry, radius_m: float = 2000.0) -> gpd.GeoDataFrame:
    bridges = _load_bridges()
    if bridges is None:
        return gpd.GeoDataFrame()
    buffer = settlement_point.buffer(radius_m)
    return bridges[bridges.geometry.intersects(buffer)]


def isolation_risk(
    settlement: str,
    settlement_point: BaseGeometry,
    inundation: BaseGeometry,
    *,
    radius_m: float = 2000.0,
) -> IsolationRisk:
    nearby = bridges_near(settlement_point, radius_m)
    dependencies = []
    at_risk = 0
    for row_id, row in nearby.iterrows():
        buffered = row.geometry.buffer(BRIDGE_BUFFER_M)
        flooded = bool(buffered.intersects(inundation))
        at_risk += int(flooded)
        name = row.get("name") if "name" in nearby.columns else None
        dependencies.append(BridgeDependency(name, str(row_id), flooded))
    total = len(nearby)
    return IsolationRisk(
        settlement=settlement,
        total_bridges=total,
        bridges_at_risk=at_risk,
        single_point_of_failure=(total == 1 and at_risk == 1),
        dependent_bridges=tuple(dependencies),
    )
