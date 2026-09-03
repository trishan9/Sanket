from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

from core.config import paths, settings
from core.errors import ConnectorError

WORKING_CRS = settings.working_crs
COG_PROFILE: dict[str, Any] = {
    "driver": "GTiff",
    "compress": "deflate",
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "BIGTIFF": "IF_SAFER",
}


def silver_dir(name: str) -> Path:
    target = paths.silver / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def reproject_raster(source_path: Path, target_path: Path, *, crs: str = WORKING_CRS) -> Path:
    with rasterio.open(source_path) as source:
        if str(source.crs) == crs:
            transform, width, height = source.transform, source.width, source.height
        else:
            transform, width, height = calculate_default_transform(
                source.crs, crs, source.width, source.height, *source.bounds
            )
        profile = (
            source.profile
            | COG_PROFILE
            | {"crs": crs, "transform": transform, "width": width, "height": height}
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(target_path, "w", **profile) as destination:
            for band in range(1, source.count + 1):
                reproject(
                    source=rasterio.band(source, band),
                    destination=rasterio.band(destination, band),
                    src_transform=source.transform,
                    src_crs=source.crs,
                    dst_transform=transform,
                    dst_crs=crs,
                    resampling=Resampling.nearest,
                )
    return target_path


def promote_rasters(dataset: str, *, pattern: str = "*.tif", crs: str = WORKING_CRS) -> list[Path]:
    source_root = paths.bronze / dataset
    if not source_root.exists():
        raise ConnectorError(f"no bronze directory for {dataset}")
    target_root = silver_dir(dataset)
    written: list[Path] = []
    for source_path in sorted(source_root.glob(pattern)):
        target_path = target_root / source_path.name
        if target_path.exists():
            written.append(target_path)
            continue
        written.append(reproject_raster(source_path, target_path, crs=crs))
    return written


def read_vector(path: Path) -> gpd.GeoDataFrame:
    import tempfile
    import zipfile

    if not zipfile.is_zipfile(path):
        return gpd.read_file(path)
    with tempfile.TemporaryDirectory() as scratch:
        with zipfile.ZipFile(path) as archive:
            archive.extractall(scratch)
        candidates = [
            found
            for suffix in ("*.geojson", "*.json", "*.shp", "*.gpkg")
            for found in Path(scratch).rglob(suffix)
        ]
        if not candidates:
            raise ConnectorError(f"no vector layer inside {path.name}")
        return gpd.read_file(candidates[0])


def promote_vectors(
    dataset: str, *, pattern: str = "*.geojson", crs: str = WORKING_CRS
) -> list[Path]:
    source_root = paths.bronze / dataset
    if not source_root.exists():
        raise ConnectorError(f"no bronze directory for {dataset}")
    target_root = silver_dir(dataset)
    written: list[Path] = []
    for source_path in sorted(source_root.glob(pattern)):
        target_path = target_root / f"{source_path.stem}.parquet"
        if target_path.exists():
            written.append(target_path)
            continue
        try:
            frame = read_vector(source_path)
        except (ConnectorError, ValueError, OSError):
            continue
        if frame.empty or frame.geometry.isna().all():
            continue
        if frame.crs is None:
            frame = frame.set_crs("EPSG:4326")
        frame.to_crs(crs).to_parquet(target_path)
        written.append(target_path)
    return written
