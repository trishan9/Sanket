from __future__ import annotations

import pytest

from api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_corridors_includes_replay_corridor_marked_as_replay(client) -> None:
    response = client.get("/api/corridors")
    body = response.get_json()
    assert "bhotekoshi.replay" in body
    assert body["bhotekoshi.replay"]["mode"] == "replay"
    assert body["bhotekoshi"]["mode"] == "live"


def test_preparedness_available_with_real_lead_times_and_caveats(client) -> None:
    response = client.get("/api/preparedness")
    body = response.get_json()
    corridor = body["corridors"]["bhotekoshi"]
    assert corridor["available"] is True
    profiles = corridor["profiles"]
    assert len(profiles) > 0
    for profile in profiles:
        assert profile["dem_vintage"]
        assert profile["caveats"]
        assert "minimum_lead_time_minutes" in profile


def test_geolibre_index_serves_the_real_bundle(client) -> None:
    response = client.get("/geolibre/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert len(response.data) > 0


def test_geolibre_asset_serves_a_real_file(client) -> None:
    response = client.get("/geolibre/geolibre-runtime-config.js")
    assert response.status_code == 200


def test_gate_screen_returns_none_for_unknown_run(client) -> None:
    response = client.get("/api/gate/no_such_run_id")
    body = response.get_json()
    assert body["gate"] is None


def test_ask_sandbox_requires_a_question(client) -> None:
    response = client.post("/api/ask", json={})
    assert response.status_code == 400


@pytest.mark.network
def test_ask_sandbox_answers_a_real_question_under_the_gevent_worker(client) -> None:
    response = client.post("/api/ask", json={"question": "what is 5 + 7?"})
    body = response.get_json()
    assert response.status_code == 200
    assert "12" in body["answer"]


def test_cors_header_present(client) -> None:
    response = client.get("/api/health")
    assert response.headers.get("Access-Control-Allow-Origin") == "*"


def test_fallback_page_stays_under_4kb_with_real_data(client) -> None:
    response = client.get("/fallback")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert len(response.data) < 4096
    assert b"Timure" in response.data


def test_charts_returns_real_lake_and_rainfall_series(client) -> None:
    response = client.get("/api/charts")
    body = response.get_json()
    assert len(body["lake_area_series"]["observations"]) > 0
    assert len(body["rainfall_series"]["observations"]) > 0
    assert body["lake_area_series"]["location"] == "Purepu glacier"


def test_geolibre_project_files_are_valid_and_distinct(tmp_path) -> None:
    import json

    from core.config import paths
    from scripts.build_geolibre_project import CAMERA_BOOKMARKS, SCENE_OVERLAP_BBOX

    west, south, east, north = SCENE_OVERLAP_BBOX
    views = set()
    for name in CAMERA_BOOKMARKS:
        target = paths.dist / f"sanket.{name}.geolibre.json"
        assert target.exists(), f"missing {target}"
        project = json.loads(target.read_text(encoding="utf-8"))
        assert len(project["layers"]) == 4
        view = project["mapView"]
        longitude, latitude = view["center"]
        assert west <= longitude <= east, f"{name} sits outside the comparable scene overlap"
        assert south <= latitude <= north, f"{name} sits outside the comparable scene overlap"
        assert view["pitch"] == 0, f"{name} is pitched; a before/after swipe must be nadir"
        views.add((longitude, latitude))
    assert len(views) == len(CAMERA_BOOKMARKS)
