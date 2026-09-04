from __future__ import annotations

import asyncio
import json

from core.state import state as default_state
from sanket_mcp.server import _demo_state, server


def test_all_twelve_tool_schemas_are_exposed() -> None:
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "search_granules",
        "detect_water_change",
        "detect_disturbance",
        "lake_area_series",
        "precip_percentile",
        "stage_volume",
        "breach_hydrograph",
        "route_flood",
        "exposure_at",
        "precedent",
        "science_lookup",
        "write_status",
    }


def test_stage_volume_returns_a_correct_real_result_over_the_protocol() -> None:
    result = asyncio.run(server.call_tool("stage_volume", {"lon": 85.377, "lat": 28.271}))
    payload = json.loads(result.content[0].text)
    assert payload["provenance"]["source"] == "NASA HMA 8 m DEM (HMA_DEM8m_MOS)"
    assert payload["value"]["max_volume_Mm3"] > 0


def test_exposure_at_returns_a_correct_real_result_over_the_protocol() -> None:
    args = {"lon": 85.30, "lat": 28.05, "radius_m": 1000}
    result = asyncio.run(server.call_tool("exposure_at", args))
    payload = json.loads(result.content[0].text)
    assert payload["provenance"]["source"] == "WorldPop 2020 + OSM/HOT"
    assert "population" in payload["value"]


def test_write_status_never_touches_the_live_board() -> None:
    settlement = "MCP-Test"
    before = default_state.statuses("bhotekoshi_trishuli")
    args = {"settlement": settlement, "basin_id": "bhotekoshi_trishuli", "level": "NORMAL"}
    asyncio.run(server.call_tool("write_status", args))
    after = default_state.statuses("bhotekoshi_trishuli")
    assert len(before) == len(after)
    demo_statuses = _demo_state().statuses("bhotekoshi_trishuli")
    assert any(s["settlement"] == settlement for s in demo_statuses)
