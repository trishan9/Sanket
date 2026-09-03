from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pyproj import Transformer
from shapely.geometry import Point

from analysis.exposure.cells import ExposureCount, exposure_at
from analysis.exposure.isolation import IsolationRisk, isolation_risk
from analysis.exposure.leadtime import SettlementLeadTime, all_lead_times
from analysis.hydro.scenarios import build_grid
from core.corridor import Corridor, Settlement

EXPOSURE_RADIUS_M = 500.0


@dataclass(frozen=True)
class PreparednessProfile:
    settlement: str
    district: str
    minimum_lead_time_minutes: float | None
    maximum_lead_time_minutes: float | None
    exposure: ExposureCount
    isolation: IsolationRisk
    dem_vintage: str
    generated_as_of: date
    caveats: tuple[str, ...]


def _lead_times_for_settlement(settlement: str, results: list[SettlementLeadTime]) -> list[float]:
    return [
        r.lead_time_minutes
        for r in results
        if r.settlement == settlement and r.lead_time_minutes is not None
    ]


def build_profile(
    settlement: Settlement,
    results: list[SettlementLeadTime],
    corridor: Corridor,
    *,
    as_of: date,
) -> PreparednessProfile:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    x, y = transformer.transform(*settlement.location)
    point = Point(x, y)
    footprint = point.buffer(EXPOSURE_RADIUS_M)

    lead_times = _lead_times_for_settlement(settlement.name, results)
    exposure = exposure_at(footprint)
    risk = isolation_risk(settlement.name, point, footprint, radius_m=2000.0)

    return PreparednessProfile(
        settlement=settlement.name,
        district=settlement.district,
        minimum_lead_time_minutes=min(lead_times) if lead_times else None,
        maximum_lead_time_minutes=max(lead_times) if lead_times else None,
        exposure=exposure,
        isolation=risk,
        dem_vintage=corridor.dem_vintage.isoformat(),
        generated_as_of=as_of,
        caveats=(
            "population is modelled 2020 usual residence, not a count, and cannot show "
            "displacement after any specific event",
            "lead times assume the current scenario grid (0.5-5.0 Mm3, 5min-6h breach); "
            "an event outside that range is not represented",
            f"the DEM predates {as_of.isoformat()} by "
            f"{as_of.year - corridor.dem_vintage.year} years or more; "
            "post-event terrain may differ",
        ),
    )


def build_all_profiles(
    corridor: Corridor, chainages: dict[str, float], *, as_of: date
) -> list[PreparednessProfile]:
    results = all_lead_times(chainages, build_grid())
    return [
        build_profile(settlement, results, corridor, as_of=as_of)
        for settlement in corridor.downstream_reach
        if settlement.name in chainages
    ]
