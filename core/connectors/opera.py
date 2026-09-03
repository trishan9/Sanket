from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import earthaccess

from core.connectors.base import FetchManifest, bronze_dir, record
from core.errors import AuthenticationError, ConnectorError

COLLECTIONS: dict[str, str] = {
    "OPERA_L3_DSWX-S1_V1": "C2949811996-POCLOUD",
    "OPERA_L3_DIST-ALERT-HLS_V1": "C2746980408-LPCLOUD",
    "OPERA_L2_RTC-S1_V1": "C2777436413-ASF",
    "HMA_DEM8m_MOS": "C3249536691-NSIDC_CPRD",
}

LICENSE = "public domain (NASA)"
SOURCE_ORG = "NASA / JPL OPERA"
INDEPENDENCE = {
    "OPERA_L3_DSWX-S1_V1": "opera_radar_water",
    "OPERA_L3_DIST-ALERT-HLS_V1": "opera_optical_disturbance",
    "OPERA_L2_RTC-S1_V1": "opera_radar_backscatter",
    "HMA_DEM8m_MOS": "hma_dem_terrain",
}
CANNOT_TELL_YOU: dict[str, list[str]] = {
    "OPERA_L3_DSWX-S1_V1": [
        "water under dense canopy or in radar layover and shadow",
        "water bodies below roughly 3000 square metres",
        "depth, volume or discharge - it is an extent product",
    ],
    "OPERA_L3_DIST-ALERT-HLS_V1": [
        "anything under cloud, which is most of the monsoon",
        "the cause of a disturbance, only that reflectance changed",
    ],
}


def login() -> None:
    if not os.environ.get("EARTHDATA_USERNAME"):
        raise AuthenticationError("EARTHDATA_USERNAME is not set")
    auth = earthaccess.login(strategy="environment", persist=False)
    if not auth.authenticated:
        raise AuthenticationError("Earthdata authentication failed")


def search(
    short_name: str,
    bbox: tuple[float, float, float, float],
    temporal: tuple[str, str] | None = None,
    count: int = 2000,
) -> list[Any]:
    kwargs: dict[str, Any] = {"short_name": short_name, "bounding_box": bbox, "count": count}
    if temporal is not None:
        kwargs["temporal"] = temporal
    try:
        return list(earthaccess.search_data(**kwargs))
    except Exception as exc:
        raise ConnectorError(f"CMR search failed for {short_name}: {exc}") from exc


def granule_dates(results: list[Any]) -> list[str]:
    import re

    seen: set[str] = set()
    for granule in results:
        for link in granule.data_links():
            found = re.search(r"_(\d{8})T\d{6}Z", link)
            if found:
                seen.add(found.group(1))
                break
    return sorted(seen)


def select_links(results: list[Any], layers: tuple[str, ...] | None) -> list[str]:
    links: list[str] = []
    for granule in results:
        for link in granule.data_links():
            if not link.endswith(".tif"):
                continue
            if layers is None or any(link.endswith(f"_{layer}.tif") for layer in layers):
                links.append(link)
    return links


def fetch(
    short_name: str,
    bbox: tuple[float, float, float, float],
    *,
    temporal: tuple[str, str] | None = None,
    as_of: date | None = None,
    limit: int | None = None,
    layers: tuple[str, ...] | None = None,
) -> FetchManifest:
    login()
    results = search(short_name, bbox, temporal)
    if limit is not None:
        results = results[-limit:]
    target = bronze_dir(short_name.lower().replace("-", "_"))
    links = select_links(results, layers)
    downloaded = earthaccess.download(links, str(target)) if links else []
    manifest = FetchManifest(
        dataset=short_name.lower().replace("-", "_"),
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"earthaccess + NASA CMR {COLLECTIONS.get(short_name, short_name)}",
        independence_group=INDEPENDENCE.get(short_name),
        bbox=bbox,
        temporal=temporal,
        cannot_tell_you=CANNOT_TELL_YOU.get(short_name, []),
        notes=[
            f"as_of filter {as_of.isoformat()}" if as_of else "no as_of filter applied",
            f"layers: {', '.join(layers)}" if layers else "all layers",
            f"granules matched: {len(results)}",
        ],
    )
    for item in downloaded:
        path = Path(item)
        if path.exists():
            manifest.files.append(record(path))
    manifest.write()
    return manifest
