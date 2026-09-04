from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Point

from analysis.economics.damage import damage_fraction_for_depth
from analysis.exposure.cells import population_within, strip_admin_fields
from core.config import paths

CELL_SIZE_M = 900.0
CELL_RADIUS_M = CELL_SIZE_M / 2.0
MIN_DEPTH_M = 0.05
WORKING_CRS = "EPSG:32645"
ACCESS_SEARCH_M = 5000.0

DAMAGED_BUILDING_WEIGHT = 12.0
HELIPAD_DISTANCE_WEIGHT = 6.0
BRIDGE_OUT_WEIGHT = 8.0

HOT_DIR = paths.silver / "hot_flood_npl"
DAMAGE_DIR = paths.silver / "hot_flood_npl_buildings_damage"

DAMAGE_LAYER = "Building damage assessment"
SEVERE_DAMAGE = frozenset({"destroyed", "major-damage"})
STANDING = "Standing"
DESTROYED = "Destroyed"

BRIDGES = "Bridges (OSM)"
HELIPADS = "Helipads (OSM)"
SCHOOLS = "Education Facilities (OSM)"
HEALTH = "Health Facilities (OSM)"
HYDROPOWER = "Exposed Hydropowers"

PRIORITY_CAVEATS: tuple[str, ...] = (
    "priority ranks relative urgency between cells: people in structures the modelled depth would "
    "damage, plus observed severe building damage, plus an access term from standing helipad "
    "distance and severed bridges; it is a triage ordering, never a casualty estimate",
    "population is WorldPop 2020 modelled usual residence, not a headcount, and cannot reflect "
    "displacement after any specific event",
    "building and bridge damage classes come from the HOT assessment over post event imagery and "
    "OSM survey tagging, not from a field survey",
    "modelled rise comes from a scenario grid routed over a DEM that predates the event",
    "the nearest health facility in the activation data sits roughly 50 km south of the corridor, "
    "so no cell has one nearby and casualties have to move down the highway",
)

SOURCES: tuple[dict[str, str], ...] = (
    {"field": "peak_rise_m", "source": "SANKET 1D routing, 1.0 Mm3 over 30 min, HMA 8 m DEM"},
    {"field": "population", "source": "WorldPop 2020 constrained, npl_ppp_2020"},
    {"field": "damaged_buildings", "source": "HOT damage assessment, 1053 buildings classified"},
    {"field": "bridges_out_5km", "source": "OSM bridges tagged Destroyed, 43 of 171 in activation"},
    {"field": "nearest_helipad_km", "source": "OSM helipads tagged Standing, 12 of 15"},
    {"field": "nearest_health_km", "source": "OSM health facilities, 5 in activation"},
    {"field": "schools_destroyed", "source": "OSM education facilities tagged Destroyed, 6 of 60"},
    {"field": "hydropower_mw", "source": "HOT exposed hydropower layer, 10 sites with capacity"},
)


@lru_cache(maxsize=16)
def _layer(name: str, damage: bool = False) -> gpd.GeoDataFrame | None:
    path = (DAMAGE_DIR if damage else HOT_DIR) / f"{name}, GeoJSON.parquet"
    if not path.exists():
        return None
    return strip_admin_fields(gpd.read_parquet(path)).to_crs(WORKING_CRS)


def _subset(name: str, geometry: Any, status: str | None = None) -> gpd.GeoDataFrame | None:
    frame = _layer(name)
    if frame is None or frame.empty:
        return None
    hits = frame.iloc[frame.sindex.query(geometry, predicate="intersects")]
    if status is not None and "status" in hits.columns:
        hits = hits[hits["status"] == status]
    return hits


def _count(name: str, geometry: Any, status: str | None = None) -> int:
    hits = _subset(name, geometry, status)
    return 0 if hits is None else int(len(hits))


def _nearest_km(name: str, centre: Point, status: str | None = None) -> float | None:
    frame = _layer(name)
    if frame is None or frame.empty:
        return None
    if status is not None and "status" in frame.columns:
        frame = frame[frame["status"] == status]
    if frame.empty:
        return None
    return round(float(frame.geometry.distance(centre).min()) / 1000.0, 2)


def _severe_damage_within(geometry: Any) -> int:
    frame = _layer(DAMAGE_LAYER, damage=True)
    if frame is None or frame.empty or "damage" not in frame.columns:
        return 0
    index = frame.sindex.query(geometry, predicate="intersects")
    if len(index) == 0:
        return 0
    return int(frame.iloc[index]["damage"].isin(SEVERE_DAMAGE).sum())


def _hydropower_mw(geometry: Any) -> float:
    hits = _subset(HYDROPOWER, geometry)
    if hits is None or hits.empty or "capacity_mw" not in hits.columns:
        return 0.0
    return round(float(hits["capacity_mw"].fillna(0).sum()), 1)


@dataclass(frozen=True)
class CorridorCell:
    longitude: float
    latitude: float
    peak_rise_m: float
    population: float
    damaged_buildings: int
    bridges_standing_5km: int
    bridges_out_5km: int
    nearest_helipad_km: float | None
    nearest_health_km: float | None
    schools: int
    schools_destroyed: int
    hydropower_mw: float
    damage_fraction: float
    priority: float


def _aggregate(band: np.ndarray, factor: int) -> np.ndarray:
    rows = band.shape[0] // factor * factor
    cols = band.shape[1] // factor * factor
    blocks = band[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    reduced: np.ndarray = blocks.max(axis=(1, 3))
    return reduced


def _access(centre: Point) -> dict[str, Any]:
    reach = centre.buffer(ACCESS_SEARCH_M)
    return {
        "bridges_standing_5km": _count(BRIDGES, reach, STANDING),
        "bridges_out_5km": _count(BRIDGES, reach, DESTROYED),
        "nearest_helipad_km": _nearest_km(HELIPADS, centre, STANDING),
        "nearest_health_km": _nearest_km(HEALTH, centre),
    }


def _cell_at(depth: float, longitude: float, latitude: float, centre: Point) -> CorridorCell:
    footprint = centre.buffer(CELL_RADIUS_M)
    population = float(population_within(footprint))
    damaged = _severe_damage_within(footprint)
    access = _access(centre)
    fraction = damage_fraction_for_depth(depth)
    helipad = access["nearest_helipad_km"] or 0.0
    severed = access["bridges_out_5km"] * BRIDGE_OUT_WEIGHT
    isolation = fraction * (helipad * HELIPAD_DISTANCE_WEIGHT + severed)
    return CorridorCell(
        longitude=longitude,
        latitude=latitude,
        peak_rise_m=round(depth, 2),
        population=round(population, 1),
        damaged_buildings=damaged,
        schools=_count(SCHOOLS, footprint),
        schools_destroyed=_count(SCHOOLS, footprint, DESTROYED),
        hydropower_mw=_hydropower_mw(footprint),
        damage_fraction=fraction,
        priority=round(fraction * population + damaged * DAMAGED_BUILDING_WEIGHT + isolation, 2),
        **access,
    )


def build_cells(slug: str = "reference_v1.0_d30_full") -> list[CorridorCell]:
    source = paths.dist / "scenario_grid" / f"{slug}_peak_rise.tif"
    if not source.exists():
        return []
    with rasterio.open(source) as dataset:
        band = dataset.read(1).astype(np.float32)
        transform, crs = dataset.transform, str(dataset.crs)
        pixel = abs(float(dataset.res[0]))
    factor = max(1, int(round(CELL_SIZE_M / pixel)))
    coarse = _aggregate(band, factor)
    to_wgs = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    to_working = Transformer.from_crs(crs, WORKING_CRS, always_xy=True)
    cells = []
    for row, col in zip(*np.where(coarse > MIN_DEPTH_M), strict=True):
        x, y = transform * ((col + 0.5) * factor, (row + 0.5) * factor)
        longitude, latitude = to_wgs.transform(x, y)
        centre = Point(*to_working.transform(x, y))
        cells.append(_cell_at(float(coarse[row, col]), float(longitude), float(latitude), centre))
    return cells


def _totals(cells: list[CorridorCell]) -> dict[str, Any]:
    health = [c.nearest_health_km for c in cells if c.nearest_health_km is not None]
    return {
        "cells": len(cells),
        "population": round(sum(c.population for c in cells)),
        "damaged_buildings": sum(c.damaged_buildings for c in cells),
        "cells_with_observed_damage": sum(1 for c in cells if c.damaged_buildings > 0),
        "max_bridges_out_5km": max((c.bridges_out_5km for c in cells), default=0),
        "schools": sum(c.schools for c in cells),
        "schools_destroyed": sum(c.schools_destroyed for c in cells),
        "hydropower_mw": round(sum(c.hydropower_mw for c in cells), 1),
        "nearest_health_km": round(min(health), 1) if health else None,
        "deepest_m": round(max((c.peak_rise_m for c in cells), default=0.0), 2),
    }


@lru_cache(maxsize=2)
def cells_geojson(slug: str = "reference_v1.0_d30_full") -> dict[str, Any]:
    cache = paths.dist / f"corridor_cells_{slug}.geojson"
    if cache.exists():
        loaded: dict[str, Any] = json.loads(cache.read_text(encoding="utf-8"))
        return loaded
    cells = build_cells(slug)
    highest = max((cell.priority for cell in cells), default=0.0)
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [cell.longitude, cell.latitude]},
                "properties": {
                    **{k: v for k, v in asdict(cell).items() if k not in {"longitude", "latitude"}},
                    "priority_normalised": round(cell.priority / highest, 4) if highest else 0.0,
                },
            }
            for cell in cells
        ],
        "cell_size_m": CELL_SIZE_M,
        "max_priority": highest,
        "totals": _totals(cells),
        "sources": list(SOURCES),
        "caveats": list(PRIORITY_CAVEATS),
    }
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return payload
