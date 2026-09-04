from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from mcp.server.mcpserver import MCPServer

from agent.tools.catalog import DISPATCH, ToolContext
from core.config import paths
from core.provenance import Evidence
from core.state import State
from core.state import state as default_state

SERVER_NAME = "sanket-mcp"
SERVER_INSTRUCTIONS = (
    "Twelve deterministic glacial-hazard tools from SANKET's own Investigator toolbox: "
    "satellite change detection, precipitation percentiles, breach hydrographs, 1D flood "
    "routing and exposure counts, all computed from real Nepal Himalaya data, never from a "
    "language model. write_status here writes to an isolated demo board, never the live "
    "SANKET board."
)

server = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

_demo_store: State | None = None


def _demo_state() -> State:
    global _demo_store
    if _demo_store is None:
        _demo_store = State(paths.dist / "mcp_demo.sqlite")
    return _demo_store


def _ctx(*, demo: bool = False) -> ToolContext:
    run_id = f"mcp_{uuid.uuid4().hex[:8]}"
    store = _demo_state() if demo else default_state
    return ToolContext(run_id, date.today(), store)


def _result(evidence: Evidence) -> dict[str, Any]:
    return {
        "ref": evidence.ref,
        "claim_type": evidence.claim_type,
        "render_style": evidence.render_style,
        "value": evidence.value,
        "provenance": evidence.provenance.model_dump(mode="json"),
    }


@server.tool()
def search_granules(product: str, lon: float, lat: float, since_days: int = 14) -> dict[str, Any]:
    args = {"product": product, "lon": lon, "lat": lat, "since_days": since_days}
    return _result(DISPATCH["search_granules"](args, _ctx()))


@server.tool()
def detect_water_change(tile: str) -> dict[str, Any]:
    return _result(DISPATCH["detect_water_change"]({"tile": tile}, _ctx()))


@server.tool()
def detect_disturbance(tile: str) -> dict[str, Any]:
    return _result(DISPATCH["detect_disturbance"]({"tile": tile}, _ctx()))


@server.tool()
def lake_area_series(lon: float, lat: float) -> dict[str, Any]:
    return _result(DISPATCH["lake_area_series"]({"lon": lon, "lat": lat}, _ctx()))


@server.tool()
def precip_percentile(target_date: str) -> dict[str, Any]:
    return _result(DISPATCH["precip_percentile"]({"target_date": target_date}, _ctx()))


@server.tool()
def stage_volume(lon: float, lat: float, dam_height_m: float = 60.0) -> dict[str, Any]:
    args = {"lon": lon, "lat": lat, "dam_height_m": dam_height_m}
    return _result(DISPATCH["stage_volume"](args, _ctx()))


@server.tool()
def breach_hydrograph(
    volume_mm3: float, duration_minutes: float, mode: str = "full"
) -> dict[str, Any]:
    args = {"volume_mm3": volume_mm3, "duration_minutes": duration_minutes, "mode": mode}
    return _result(DISPATCH["breach_hydrograph"](args, _ctx()))


@server.tool()
def route_flood(volume_mm3: float, duration_minutes: float, mode: str = "full") -> dict[str, Any]:
    args = {"volume_mm3": volume_mm3, "duration_minutes": duration_minutes, "mode": mode}
    return _result(DISPATCH["route_flood"](args, _ctx()))


@server.tool()
def exposure_at(lon: float, lat: float, radius_m: float = 500.0) -> dict[str, Any]:
    args = {"lon": lon, "lat": lat, "radius_m": radius_m}
    return _result(DISPATCH["exposure_at"](args, _ctx()))


@server.tool()
def precedent(country: str) -> dict[str, Any]:
    return _result(DISPATCH["precedent"]({"country": country}, _ctx()))


@server.tool()
def science_lookup(query: str) -> dict[str, Any]:
    return _result(DISPATCH["science_lookup"]({"query": query}, _ctx()))


@server.tool()
def write_status(settlement: str, basin_id: str, level: str) -> dict[str, Any]:
    args = {"settlement": settlement, "basin_id": basin_id, "level": level}
    return _result(DISPATCH["write_status"](args, _ctx(demo=True)))


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
