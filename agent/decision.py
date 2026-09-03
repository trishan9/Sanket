from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from core.board import Level
from core.config import settings

Confidence = Literal["high", "medium", "low", "insufficient"]

W_MAGNITUDE = 0.40
W_LEAD_TIME = 0.35
W_EXPOSURE = 0.20
W_CONFIDENCE = 0.15

CONFIDENCE_SCORE: dict[Confidence, float] = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.0,
    "insufficient": -1.0,
}

EXPOSURE_REFERENCE = 2000.0
WATCH_THRESHOLD = 0.30
ALERT_THRESHOLD = 0.65
FLIP_SEARCH_TOLERANCE = 1e-3


@dataclass(frozen=True)
class Contribution:
    term: str
    raw_value: str
    weight: float
    contribution: float


@dataclass(frozen=True)
class DecisionInputs:
    change_magnitude_z: float
    min_lead_time_minutes: float | None
    exposure_count: int
    confidence: Confidence
    vetoed: bool


@dataclass(frozen=True)
class Decision:
    status: Level
    score: float
    contributions: tuple[Contribution, ...]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _magnitude_term(z: float) -> Contribution:
    fraction = _clamp(z / settings.escalation_z)
    return Contribution("change magnitude", f"z={z:.2f}", W_MAGNITUDE, fraction * W_MAGNITUDE)


def _lead_time_term(minutes: float | None) -> Contribution:
    if minutes is None:
        return Contribution("minimum lead time", "no route computed", W_LEAD_TIME, 0.0)
    fraction = _clamp(1.0 - minutes / settings.lead_time_threshold_minutes)
    return Contribution(
        "minimum lead time", f"{minutes:.0f} min", W_LEAD_TIME, fraction * W_LEAD_TIME
    )


def _exposure_term(count: int) -> Contribution:
    fraction = _clamp(math.log1p(count) / math.log1p(EXPOSURE_REFERENCE))
    return Contribution("exposure count", str(count), W_EXPOSURE, fraction * W_EXPOSURE)


def _confidence_term(confidence: Confidence) -> Contribution:
    value = CONFIDENCE_SCORE[confidence]
    return Contribution("confidence", confidence, W_CONFIDENCE, value * W_CONFIDENCE)


def _status_for_score(score: float) -> Level:
    if score >= ALERT_THRESHOLD:
        return "ALERT"
    if score >= WATCH_THRESHOLD:
        return "WATCH"
    return "NORMAL"


def decide(inputs: DecisionInputs) -> Decision:
    if inputs.vetoed:
        return Decision("INSUFFICIENT", 0.0, ())
    contributions = (
        _magnitude_term(inputs.change_magnitude_z),
        _lead_time_term(inputs.min_lead_time_minutes),
        _exposure_term(inputs.exposure_count),
        _confidence_term(inputs.confidence),
    )
    score = sum(c.contribution for c in contributions)
    return Decision(_status_for_score(score), score, contributions)


Replacer = Callable[[DecisionInputs, float], DecisionInputs]


def _replace_z(inputs: DecisionInputs, z: float) -> DecisionInputs:
    return DecisionInputs(
        z, inputs.min_lead_time_minutes, inputs.exposure_count, inputs.confidence, inputs.vetoed
    )


def _replace_lead_time(inputs: DecisionInputs, minutes: float) -> DecisionInputs:
    return DecisionInputs(
        inputs.change_magnitude_z,
        minutes,
        inputs.exposure_count,
        inputs.confidence,
        inputs.vetoed,
    )


def _replace_exposure(inputs: DecisionInputs, count: float) -> DecisionInputs:
    return DecisionInputs(
        inputs.change_magnitude_z,
        inputs.min_lead_time_minutes,
        round(count),
        inputs.confidence,
        inputs.vetoed,
    )


def _search_flip(
    inputs: DecisionInputs, replace: Replacer, from_value: float, toward_value: float
) -> float | None:
    base_status = decide(inputs).status
    if decide(replace(inputs, toward_value)).status == base_status:
        return None
    a, b = from_value, toward_value
    for _ in range(40):
        mid = (a + b) / 2
        if decide(replace(inputs, mid)).status == base_status:
            a = mid
        else:
            b = mid
        if abs(b - a) < FLIP_SEARCH_TOLERANCE:
            break
    return b


def flip_points(inputs: DecisionInputs) -> dict[str, float | None]:
    lead_time = inputs.min_lead_time_minutes or 0.0
    return {
        "change_magnitude_z": _search_flip(inputs, _replace_z, inputs.change_magnitude_z, 0.0),
        "min_lead_time_minutes": _search_flip(
            inputs, _replace_lead_time, lead_time, settings.lead_time_threshold_minutes * 6
        ),
        "exposure_count": _search_flip(
            inputs, _replace_exposure, float(inputs.exposure_count), 0.0
        ),
    }
