from __future__ import annotations

from analysis.risk.base_rates import _inventory
from analysis.risk.schemas import ObservabilityReport, ObservabilityState

DETECTION_LIMIT_KM2 = 0.003
ATTENTION_THRESHOLD_KM2 = 0.01
THAME_2024_AREA_KM2 = 0.05

NOT_OBSERVABLE_CAVEATS: tuple[str, ...] = (
    "below the detection limit we report not observable, never not present",
    "a lake can form and drain entirely between two satellite passes, as apparently "
    "happened at Purepu in July 2023",
    f"the lake that failed at Thame in 2024 was about {THAME_2024_AREA_KM2} km2, well above "
    "this detection limit but below the size conventional inventories reliably track",
    "optical scenes are cloud-blocked for much of the monsoon; radar coverage is sparser",
)


def classify_area(area_km2: float | None) -> ObservabilityState:
    if area_km2 is None:
        return "no_coverage"
    if area_km2 <= DETECTION_LIMIT_KM2:
        return "below_detection_limit"
    return "observable"


def observability_report(catchment: str) -> ObservabilityReport:
    inventory = _inventory()
    basin = inventory
    if "Basin" in inventory.columns:
        matched = inventory[inventory["Basin"].astype(str).str.lower() == catchment.lower()]
        if len(matched) > 0:
            basin = matched
    areas = basin["Area"].astype(float)
    states = {
        str(row.GL_ID): classify_area(float(row.Area))
        for row in basin.head(200).itertuples()
        if hasattr(row, "GL_ID")
    }
    return ObservabilityReport(
        catchment=catchment,
        inventoried_lakes=int(len(basin)),
        below_detection_limit=int((areas <= DETECTION_LIMIT_KM2).sum()),
        below_attention_threshold=int((areas <= ATTENTION_THRESHOLD_KM2).sum()),
        detection_limit_km2=DETECTION_LIMIT_KM2,
        attention_threshold_km2=ATTENTION_THRESHOLD_KM2,
        smallest_inventoried_km2=float(areas.min()) if len(areas) else 0.0,
        states=states,
        caveats=NOT_OBSERVABLE_CAVEATS,
    )
