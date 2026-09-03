from __future__ import annotations

from datetime import date
from typing import Any

from pystac_client import Client

from core.connectors.base import FetchManifest, bronze_dir, download
from core.errors import ConnectorError

PLANETARY_COMPUTER = "https://planetarycomputer.microsoft.com/api/stac/v1"
SIGN_ENDPOINT = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

LICENSES = {
    "sentinel-2-l2a": "CC-BY-4.0 (Copernicus)",
    "sentinel-1-grd": "CC-BY-4.0 (Copernicus)",
    "cop-dem-glo-30": "CC-BY-4.0 (Copernicus)",
}
INDEPENDENCE = {
    "sentinel-2-l2a": "sanket_optical",
    "sentinel-1-grd": "sanket_radar",
    "cop-dem-glo-30": "copernicus_dem_terrain",
}
CANNOT_TELL_YOU = {
    "sentinel-2-l2a": [
        "anything under cloud, and the monsoon window here is 38 to 99 percent cloud",
        "water bodies below roughly 0.003 square kilometres",
    ],
    "sentinel-1-grd": [
        "the valley floor where layover and shadow obliterate it in steep terrain",
        "water depth - backscatter gives extent, not volume",
    ],
}


def client() -> Client:
    return Client.open(PLANETARY_COMPUTER)


def search_items(
    collection: str, bbox: tuple[float, float, float, float], window: str, limit: int | None = None
) -> list[Any]:
    try:
        search = client().search(collections=[collection], bbox=list(bbox), datetime=window)
        items = sorted(search.items(), key=lambda item: item.datetime or "")
    except Exception as exc:
        raise ConnectorError(f"STAC search failed for {collection}: {exc}") from exc
    return items[:limit] if limit else items


def item_summary(items: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "datetime": item.datetime.isoformat(),
            "cloud_cover": item.properties.get("eo:cloud_cover"),
            "orbit_state": item.properties.get("sat:orbit_state"),
            "platform": item.properties.get("platform"),
        }
        for item in items
    ]


def sign(href: str) -> str:
    from core.connectors.base import get_json

    payload = get_json(SIGN_ENDPOINT, params={"href": href})
    signed: str = payload.get("href", href)
    return signed


def fetch_assets(
    collection: str,
    bbox: tuple[float, float, float, float],
    window: str,
    assets: tuple[str, ...],
    *,
    limit: int | None = None,
    as_of: date | None = None,
) -> FetchManifest:
    items = search_items(collection, bbox, window, limit)
    target = bronze_dir(collection.replace("-", "_"))
    manifest = FetchManifest(
        dataset=collection.replace("-", "_"),
        source_org="Microsoft Planetary Computer / ESA Copernicus",
        license=LICENSES.get(collection, "see collection metadata"),
        access=f"STAC {PLANETARY_COMPUTER} collection {collection}",
        independence_group=INDEPENDENCE.get(collection),
        bbox=bbox,
        temporal=(window.split("/")[0], window.split("/")[-1]),
        cannot_tell_you=CANNOT_TELL_YOU.get(collection, []),
        notes=[
            f"items matched: {len(items)}",
            f"assets: {', '.join(assets)}",
            f"as_of filter {as_of.isoformat()}" if as_of else "no as_of filter applied",
        ],
    )
    for item in items:
        for name in assets:
            asset = item.assets.get(name)
            if asset is None:
                continue
            filename = f"{item.id}_{name}.tif"
            manifest.files.append(
                download(sign(asset.href), target / filename, dataset=manifest.dataset)
            )
    manifest.write()
    return manifest
