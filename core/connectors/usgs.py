from __future__ import annotations

from datetime import date

from core.connectors.base import FetchManifest, get_json

FDSN = "https://earthquake.usgs.gov/fdsnws/event/1/query"
LICENSE = "public domain (USGS)"
SOURCE_ORG = "USGS ANSS Comprehensive Catalog"


def events_near(
    lon: float,
    lat: float,
    *,
    radius_km: float = 100.0,
    start: date,
    end: date,
    min_magnitude: float = 3.0,
) -> list[dict[str, object]]:
    payload = get_json(
        FDSN,
        params={
            "format": "geojson",
            "starttime": start.isoformat(),
            "endtime": end.isoformat(),
            "longitude": lon,
            "latitude": lat,
            "maxradiuskm": radius_km,
            "minmagnitude": min_magnitude,
        },
    )
    return [
        {
            "id": feature["id"],
            "time": feature["properties"]["time"],
            "mag": feature["properties"]["mag"],
            "type": feature["properties"].get("type"),
            "place": feature["properties"].get("place"),
        }
        for feature in payload.get("features", [])
    ]


def manifest(lon: float, lat: float, start: date, end: date) -> FetchManifest:
    events = events_near(lon, lat, start=start, end=end)
    return FetchManifest(
        dataset="usgs_anss",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=FDSN,
        claim_type="observation",
        notes=[f"{len(events)} events within 100 km, {start}..{end}"],
        cannot_tell_you=[
            "whether a seismic-looking event was a true earthquake or a landslide - "
            "USGS itself reclassified the 26 Aug 2026 event after the fact",
        ],
    )
