from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from core.errors import ConnectorError

GDAL_ENV: dict[str, object] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.cog,.TIF",
    "GDAL_HTTP_MAX_RETRY": 3,
    "GDAL_HTTP_RETRY_DELAY": 2,
    "VSI_CACHE": True,
    "GDAL_CACHEMAX": 128,
}


def clip_remote(url: str, bbox: tuple[float, float, float, float], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with rasterio.Env(**GDAL_ENV), rasterio.open(url) as source:
            left, bottom, right, top = transform_bounds("EPSG:4326", source.crs, *bbox)
            window = from_bounds(left, bottom, right, top, source.transform)
            window = window.round_offsets().round_lengths()
            if window.width < 1 or window.height < 1:
                raise ConnectorError(f"clip window is empty for {url}")
            data = source.read(1, window=window)
            profile = source.profile | {
                "height": data.shape[0],
                "width": data.shape[1],
                "transform": source.window_transform(window),
                "driver": "GTiff",
                "compress": "deflate",
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
            }
            if data.shape[0] < 256 or data.shape[1] < 256:
                profile.pop("blockxsize", None)
                profile.pop("blockysize", None)
                profile["tiled"] = False
            with rasterio.open(target, "w", **profile) as destination:
                destination.write(data, 1)
    except rasterio.RasterioIOError as exc:
        raise ConnectorError(f"failed to clip {url}: {exc}") from exc
    return target


def clip_local(source_path: Path, bbox: tuple[float, float, float, float], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(source_path) as source:
        left, bottom, right, top = transform_bounds("EPSG:4326", source.crs, *bbox)
        window = from_bounds(left, bottom, right, top, source.transform)
        window = window.round_offsets().round_lengths()
        data = source.read(1, window=window)
        profile = source.profile | {
            "height": data.shape[0],
            "width": data.shape[1],
            "transform": source.window_transform(window),
            "driver": "GTiff",
            "compress": "deflate",
            "tiled": False,
        }
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        with rasterio.open(target, "w", **profile) as destination:
            destination.write(data, 1)
    return target
