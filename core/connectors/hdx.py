from __future__ import annotations

from typing import Any

from core.connectors.base import FetchManifest, bronze_dir, download, get_json
from core.errors import ConnectorError

CKAN = "https://data.humdata.org/api/3/action"
LICENSE_DEFAULT = "see per-dataset licence; OSM-derived layers are ODbL-1.0"

INDEPENDENCE = {
    "hot_flood_npl": "hot_osm_mapping",
    "hot_flood_npl_buildings_damage": "cv_damage_vhr",
}
CANNOT_TELL_YOU = {
    "hot_flood_npl_buildings_damage": [
        "severity, occupancy or casualties - it is a binary damage flag",
        "anything under cloud, tree canopy or debris",
        "buildings absent from the footprint layer never enter any score",
    ],
    "hot_flood_npl": [
        "areas mappers had not yet reached at the time of extraction",
    ],
}


def package(dataset_id: str) -> dict[str, Any]:
    payload = get_json(f"{CKAN}/package_show", params={"id": dataset_id})
    if not payload.get("success"):
        raise ConnectorError(f"HDX package_show failed for {dataset_id}")
    result: dict[str, Any] = payload["result"]
    return result


def fetch(
    dataset_id: str,
    *,
    formats: tuple[str, ...] = ("GeoJSON", "SHP", "CSV", "GPKG"),
    limit: int | None = None,
) -> FetchManifest:
    meta = package(dataset_id)
    target = bronze_dir(dataset_id)
    manifest = FetchManifest(
        dataset=dataset_id,
        source_org=meta.get("organization", {}).get("title", "HDX"),
        license=meta.get("license_title", LICENSE_DEFAULT),
        access=f"HDX CKAN package {dataset_id}",
        independence_group=INDEPENDENCE.get(dataset_id),
        claim_type="model_output" if "damage" in dataset_id else "observation",
        cannot_tell_you=CANNOT_TELL_YOU.get(dataset_id, []),
        notes=[f"hdx last modified: {meta.get('last_modified') or meta.get('metadata_modified')}"],
    )
    resources = [
        r
        for r in meta.get("resources", [])
        if r.get("format", "").upper() in {f.upper() for f in formats}
    ]
    for resource in resources[:limit] if limit else resources:
        name = resource.get("name") or resource["url"].rsplit("/", 1)[-1]
        if "." not in name:
            name = f"{name}.{resource.get('format', 'bin').lower()}"
        try:
            manifest.files.append(download(resource["url"], target / name, dataset=dataset_id))
        except Exception as exc:
            manifest.notes.append(f"skipped {name}: {type(exc).__name__}")
    manifest.write()
    return manifest


def list_resources(dataset_id: str) -> list[dict[str, Any]]:
    return [
        {"name": r.get("name"), "format": r.get("format"), "size": r.get("size")}
        for r in package(dataset_id).get("resources", [])
    ]
