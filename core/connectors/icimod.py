from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from core.config import paths
from core.connectors.base import FetchManifest, record
from core.errors import ConnectorError

MANUAL_ROOT = paths.bronze / "manual" / "icimod"
LICENSE = "ICIMOD RDS data download agreement, research use"
SOURCE_ORG = "ICIMOD / UNDP"
DOI_PDGL = "10.26066/RDS.1971950"
DOI_INVENTORY = "10.26066/RDS.1971946"


def _find(pattern: str) -> Path:
    matches = sorted(MANUAL_ROOT.rglob(pattern))
    if not matches:
        raise ConnectorError(
            f"ICIMOD file {pattern} not found under {MANUAL_ROOT}; see MANUAL_DOWNLOADS.md B1"
        )
    return matches[0]


def read_pdgl() -> gpd.GeoDataFrame:
    return gpd.read_file(_find("PDGLs.shp"))


def read_inventory() -> gpd.GeoDataFrame:
    return gpd.read_file(_find("GL_3basins_2015.shp"))


def build_manifest() -> FetchManifest:
    pdgl_path, inventory_path = _find("PDGLs.shp"), _find("GL_3basins_2015.shp")
    pdgl, inventory = read_pdgl(), read_inventory()
    manifest = FetchManifest(
        dataset="icimod_glacial_lakes",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"manual download, DOI {DOI_PDGL} and {DOI_INVENTORY}",
        independence_group="icimod_inventory",
        claim_type="observation",
        notes=[
            f"PDGLs: {len(pdgl)} ({pdgl.Country.value_counts().to_dict()})",
            f"inventory 2015: {len(inventory)} lakes",
            "inventory epoch is 2015; lakes formed since are absent by construction",
        ],
        cannot_tell_you=[
            "lakes that formed after the 2015 inventory epoch",
            "lakes below the imagery detection floor of roughly 0.003 square kilometres",
            "whether a listed lake is currently impounding water - it is a static inventory",
            "the 2026 Lhende source: 25 lakes sit in that catchment and none is PDGL-listed",
        ],
    )
    for path in (pdgl_path, inventory_path):
        for sibling in sorted(path.parent.glob(f"{path.stem}.*")):
            manifest.files.append(record(sibling))
    manifest.write()
    return manifest


def to_silver() -> tuple[Path, Path]:
    target = paths.silver / "icimod"
    target.mkdir(parents=True, exist_ok=True)
    pdgl_out = target / "pdgl.parquet"
    inventory_out = target / "glacial_lakes_2015.parquet"
    read_pdgl().to_parquet(pdgl_out)
    read_inventory().to_parquet(inventory_out)
    return pdgl_out, inventory_out


def clip_bbox(frame: gpd.GeoDataFrame, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
    min_x, min_y, max_x, max_y = bbox
    key = (slice(min_x, max_x), slice(min_y, max_y))
    result: gpd.GeoDataFrame = frame.cx[key]
    return result


def source_catchment_gap(bbox: tuple[float, float, float, float]) -> dict[str, object]:
    inventory = read_inventory()
    pdgl_ids = set(read_pdgl().GL_ID)
    clipped = clip_bbox(inventory, bbox)
    return {
        "lakes_in_catchment": int(len(clipped)),
        "pdgl_listed": int(clipped.GL_ID.isin(pdgl_ids).sum()),
        "in_china": int((clipped.Country == "China").sum()),
        "median_area_km2": float(clipped.Area.median()) if len(clipped) else 0.0,
        "max_area_km2": float(clipped.Area.max()) if len(clipped) else 0.0,
    }
