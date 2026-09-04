from __future__ import annotations

import json
from typing import Any

from geolibre import Map

from core.config import paths

VANTOR_BASE = "https://vantor-opendata.s3.amazonaws.com/events/Nepal-Flooding-Aug-2026"
VANTOR_PRE_EVENT = f"{VANTOR_BASE}/10500100364E8400.tif"
VANTOR_POST_EVENT = f"{VANTOR_BASE}/B040001100882F10.tif"
OUR_COG_RELATIVE = "scenario_grid/reference_v1.0_d30_full_peak_rise.tif"
LAKE_POLYGONS_RELATIVE = "lake_polygons.geojson"

SCENE_OVERLAP_BBOX = (85.266, 28.108, 85.413, 28.261)

CAMERA_BOOKMARKS: dict[str, dict[str, float]] = {
    "overlap_extent": {"lng": 85.340, "lat": 28.185, "zoom": 11.6, "bearing": 0, "pitch": 0},
    "syapru_besi": {"lng": 85.3372, "lat": 28.1611, "zoom": 14.0, "bearing": 0, "pitch": 0},
    "upper_reach": {"lng": 85.345, "lat": 28.230, "zoom": 13.2, "bearing": 0, "pitch": 0},
}


def _build_layers(data_base_url: str) -> dict[str, Any]:
    m = Map()
    pre = m.add_cog(VANTOR_PRE_EVENT, name="Vantor pre-event (2023-09-17)")
    post = m.add_cog(VANTOR_POST_EVENT, name="Vantor post-event (2026-08-27)")
    m.add_cog(
        f"{data_base_url}/{OUR_COG_RELATIVE}",
        name="Modelled inundation (peak rise, v1.0 Mm3 / 30 min)",
        colormap="magma",
    )
    lake_polygons = json.loads((paths.dist / LAKE_POLYGONS_RELATIVE).read_text(encoding="utf-8"))
    m.add_geojson(lake_polygons, name="Glacial lakes (ICIMOD inventory)")
    m.split_map(left_layers=pre, right_layers=post)
    return m.to_project()


def build_all(data_base_url: str = "http://127.0.0.1:5000/data") -> dict[str, dict[str, Any]]:
    projects: dict[str, dict[str, Any]] = {}
    for bookmark_name, view in CAMERA_BOOKMARKS.items():
        project = _build_layers(data_base_url)
        project["name"] = f"SANKET - Bhotekoshi corridor - {bookmark_name}"
        project["mapView"] = {
            "center": [view["lng"], view["lat"]],
            "zoom": view["zoom"],
            "bearing": view["bearing"],
            "pitch": view["pitch"],
        }
        target = paths.dist / f"sanket.{bookmark_name}.geolibre.json"
        target.write_text(json.dumps(project, default=str, indent=2), encoding="utf-8")
        projects[bookmark_name] = project
    return projects


if __name__ == "__main__":
    result = build_all()
    for name in result:
        print(f"wrote dist/sanket.{name}.geolibre.json")
