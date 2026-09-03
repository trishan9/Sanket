from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from actions.levels import RiskLevel
from core.corridor import Corridor
from core.errors import ConnectorError
from core.state import State

FLASH_MAX_STEPS = 4
FLASH_LABEL = "FAST PATH"
FLASH_CONFIDENCE_TIER = "reduced (fast path, fewer observations by design)"
FLASH_GATE_DEADLINE_MINUTES = 8

STAGE_RATE_THRESHOLD_M_PER_30MIN = 0.5
RAINFALL_INTENSITY_THRESHOLD_MM_PER_60MIN = 30.0
DISTURBANCE_JUMP_THRESHOLD_KM2 = 0.5
SEISMIC_MIN_MAGNITUDE = 4.0
SEISMIC_RADIUS_KM = 60.0

LANDSLIDE_EVENT_TYPES: frozenset[str] = frozenset(
    {"landslide", "rock slide", "rockslide", "debris flow", "mine collapse", "other event"}
)

FLASH_TOOLS: tuple[str, ...] = ("exposure_at", "route_flood", "breach_hydrograph")

FLASH_SYSTEM_PROMPT = (
    "You are Investigator running the SANKET FAST PATH. A rate-of-change trigger has fired "
    "and you have four steps only. Do exposure and arrival time, nothing else. Call "
    "exposure_at for the settlements at risk and route_flood for arrival timing, propose one "
    "claim citing those refs, then conclude. You are running on deliberately less evidence "
    "than a normal investigation, so state that the confidence is reduced. You may not state "
    "that an outburst is likely or imminent. Routing outputs are scenario claims, never "
    "predictions."
)


@dataclass(frozen=True)
class FlashTrigger:
    kind: str
    detected: bool
    value: float
    threshold: float
    detail: str
    source: str

    def rendered(self) -> str:
        state = "fired" if self.detected else "quiet"
        return f"{FLASH_LABEL} {self.kind} {state}: {self.detail}"


@dataclass(frozen=True)
class FlashAssessment:
    corridor_basin_id: str
    triggers: tuple[FlashTrigger, ...]
    fired: bool
    level: RiskLevel
    confidence_tier: str
    gate_deadline_minutes: int

    @property
    def fired_kinds(self) -> tuple[str, ...]:
        return tuple(t.kind for t in self.triggers if t.detected)

    def rendered(self) -> str:
        if not self.fired:
            return f"{FLASH_LABEL} not triggered for {self.corridor_basin_id}"
        return (
            f"{FLASH_LABEL} triggered for {self.corridor_basin_id} by "
            f"{', '.join(self.fired_kinds)}; proposed level {self.level}, "
            f"confidence {self.confidence_tier}"
        )


def seismic_landslide_trigger(corridor: Corridor, as_of: date) -> FlashTrigger:
    from core.connectors.usgs import events_near

    lon, lat = corridor.feature(corridor.watched_features[0].id).location
    try:
        events = events_near(
            lon,
            lat,
            radius_km=SEISMIC_RADIUS_KM,
            start=as_of - timedelta(days=1),
            end=as_of + timedelta(days=1),
            min_magnitude=SEISMIC_MIN_MAGNITUDE,
        )
    except (ConnectorError, OSError) as exc:
        return FlashTrigger(
            kind="seismic_landslide",
            detected=False,
            value=0.0,
            threshold=SEISMIC_MIN_MAGNITUDE,
            detail=f"ANSS unreachable ({type(exc).__name__}); not observable, not absent",
            source="USGS ANSS",
        )
    return _seismic_trigger_from(events)


def _seismic_trigger_from(events: list[dict[str, object]]) -> FlashTrigger:
    landslides = [
        event for event in events if str(event.get("type", "")).lower() in LANDSLIDE_EVENT_TYPES
    ]
    magnitudes = [float(str(e.get("mag") or 0.0)) for e in landslides]
    best = max(magnitudes, default=0.0)
    detail = (
        f"{len(landslides)} landslide-type event(s) within {SEISMIC_RADIUS_KM:.0f} km, "
        f"largest M{best:.1f}"
        if landslides
        else f"{len(events)} seismic event(s) in window, none classified landslide-type"
    )
    return FlashTrigger(
        kind="seismic_landslide",
        detected=bool(landslides),
        value=best,
        threshold=SEISMIC_MIN_MAGNITUDE,
        detail=detail,
        source="USGS ANSS Comprehensive Catalog",
    )


def stage_rate_trigger(rise_m: float, minutes: float) -> FlashTrigger:
    scaled = rise_m * (30.0 / minutes) if minutes > 0 else 0.0
    return FlashTrigger(
        kind="stage_rate",
        detected=scaled >= STAGE_RATE_THRESHOLD_M_PER_30MIN,
        value=scaled,
        threshold=STAGE_RATE_THRESHOLD_M_PER_30MIN,
        detail=f"{scaled:.2f} m per 30 min against {STAGE_RATE_THRESHOLD_M_PER_30MIN} m",
        source="DHM gauge",
    )


def rainfall_intensity_trigger(mm: float, minutes: float) -> FlashTrigger:
    scaled = mm * (60.0 / minutes) if minutes > 0 else 0.0
    return FlashTrigger(
        kind="rainfall_intensity",
        detected=scaled >= RAINFALL_INTENSITY_THRESHOLD_MM_PER_60MIN,
        value=scaled,
        threshold=RAINFALL_INTENSITY_THRESHOLD_MM_PER_60MIN,
        detail=(
            f"{scaled:.1f} mm per 60 min against "
            f"{RAINFALL_INTENSITY_THRESHOLD_MM_PER_60MIN} mm"
        ),
        source="CHIRPS preliminary daily, disaggregated",
    )


def disturbance_jump_trigger(delta_km2: float) -> FlashTrigger:
    return FlashTrigger(
        kind="disturbance_jump",
        detected=delta_km2 >= DISTURBANCE_JUMP_THRESHOLD_KM2,
        value=delta_km2,
        threshold=DISTURBANCE_JUMP_THRESHOLD_KM2,
        detail=f"{delta_km2:.3f} km2 new confirmed disturbance against "
        f"{DISTURBANCE_JUMP_THRESHOLD_KM2} km2",
        source="OPERA DIST-ALERT-HLS",
    )


def _level_for(triggers: tuple[FlashTrigger, ...]) -> RiskLevel:
    fired = [t for t in triggers if t.detected]
    if not fired:
        return "GREEN"
    kinds = {t.kind for t in fired}
    if "seismic_landslide" in kinds or len(fired) >= 2:
        return "RED"
    return "ORANGE"


def assess(corridor: Corridor, triggers: tuple[FlashTrigger, ...]) -> FlashAssessment:
    level = _level_for(triggers)
    return FlashAssessment(
        corridor_basin_id=corridor.basin_id,
        triggers=triggers,
        fired=any(t.detected for t in triggers),
        level=level,
        confidence_tier=FLASH_CONFIDENCE_TIER,
        gate_deadline_minutes=FLASH_GATE_DEADLINE_MINUTES,
    )


def escalation_deadline(requested_at: datetime | None = None) -> datetime:
    start = requested_at or datetime.now(UTC)
    return start + timedelta(minutes=FLASH_GATE_DEADLINE_MINUTES)


def is_escalation_due(requested_at: datetime, now: datetime | None = None) -> bool:
    return (now or datetime.now(UTC)) >= escalation_deadline(requested_at)


def escalate_unanswered_gate(
    run_id: str, requested_at: datetime, store: State | None = None
) -> str | None:
    from actions import gate
    from core.contacts import load_institutional_contacts

    if not is_escalation_due(requested_at):
        return None
    contacts = [c for c in load_institutional_contacts() if c.role != "ddmc_duty_officer"]
    if not contacts:
        return None
    nominee = contacts[0]
    return gate.record_notification(
        "flash_gate_escalation",
        nominee.channel,
        nominee.contact,
        run_id,
        "escalated_unanswered",
        store=store,
    )
