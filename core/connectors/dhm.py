from __future__ import annotations

from core.connectors.base import FetchManifest
from core.errors import ConnectorError

LICENSE = "not applicable - no public API"
SOURCE_ORG = "Department of Hydrology and Meteorology, Nepal"

NOTE = (
    "DHM river watch has no public API - it publishes stage readings as web pages, "
    "not a machine-readable feed. The brief names this the weakest trigger by design: "
    "a downstream gauge reports a flood already in progress. This connector is a stub "
    "that raises rather than silently returning nothing, so a missing gauge feed is "
    "visible in the trace instead of looking like a clean zero."
)


def stage_above_threshold(gauge_id: str) -> bool:
    raise ConnectorError(
        f"DHM gauge {gauge_id}: no public API. {NOTE} "
        "See MANUAL_DOWNLOADS.md for the hand-curated CSV fallback."
    )


def manifest() -> FetchManifest:
    return FetchManifest(
        dataset="dhm_river_watch",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access="web pages, not an API - hand-curated CSV only",
        claim_type="observation",
        notes=[NOTE],
        cannot_tell_you=[
            "anything upstream of the gauge - it is a confirmation channel, not early warning",
            "a machine-readable real-time feed - none exists",
        ],
    )
