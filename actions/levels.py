from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.board import Level as LegacyLevel

RiskLevel = Literal["GREEN", "YELLOW", "ORANGE", "RED", "GREY"]

RISK_LEVELS: tuple[RiskLevel, ...] = ("GREEN", "YELLOW", "ORANGE", "RED", "GREY")

LEGACY_TO_RISK: dict[str, RiskLevel] = {
    "NORMAL": "GREEN",
    "WATCH": "YELLOW",
    "ALERT": "RED",
    "INSUFFICIENT": "GREY",
}

RISK_TO_LEGACY: dict[RiskLevel, LegacyLevel] = {
    "GREEN": "NORMAL",
    "YELLOW": "WATCH",
    "ORANGE": "ALERT",
    "RED": "ALERT",
    "GREY": "INSUFFICIENT",
}

RISK_ORDER: dict[RiskLevel, int] = {
    "GREEN": 0,
    "GREY": 1,
    "YELLOW": 2,
    "ORANGE": 3,
    "RED": 4,
}

AUTONOMOUS_RISK_CEILING: RiskLevel = "YELLOW"

RISK_NEPALI: dict[RiskLevel, str] = {
    "GREEN": "सामान्य",
    "YELLOW": "निगरानी",
    "ORANGE": "उच्च सतर्कता",
    "RED": "तत्काल खतरा",
    "GREY": "मूल्याङ्कन असम्भव",
}

RISK_ENGLISH_ACTION: dict[RiskLevel, str] = {
    "GREEN": "No action needed now.",
    "YELLOW": "Stay alert. Be ready to move.",
    "ORANGE": "Prepare to evacuate now. Move valuables and livestock to high ground.",
    "RED": "Move to high ground immediately. Do not cross the river.",
    "GREY": "Evidence is insufficient to assess. Treat with caution and await update.",
}

RISK_NEPALI_ACTION: dict[RiskLevel, str] = {
    "GREEN": "अहिले कुनै कारबाही आवश्यक छैन।",
    "YELLOW": "सतर्क रहनुहोस्। सर्न तयार रहनुहोस्।",
    "ORANGE": "अहिले नै सर्ने तयारी गर्नुहोस्। सामान र पशुधन अग्लो ठाउँमा लैजानुहोस्।",
    "RED": "तुरुन्त अग्लो ठाउँमा जानुहोस्। नदी नतर्नुहोस्।",
    "GREY": "प्रमाण अपर्याप्त छ। सावधान रहनुहोस् र अद्यावधिक पर्खनुहोस्।",
}

RISK_HEX: dict[RiskLevel, str] = {
    "GREEN": "#1f8a4c",
    "YELLOW": "#d8a11a",
    "ORANGE": "#e0692a",
    "RED": "#c0212f",
    "GREY": "#5c6470",
}


@dataclass(frozen=True)
class SettlementLevel:
    settlement: str
    level: RiskLevel
    reason: str
    lead_time_minutes: float | None = None


CANONICAL: dict[str, RiskLevel] = {
    "GREEN": "GREEN",
    "YELLOW": "YELLOW",
    "ORANGE": "ORANGE",
    "RED": "RED",
    "GREY": "GREY",
}


def coerce_level(value: str) -> RiskLevel:
    upper = value.strip().upper()
    direct = CANONICAL.get(upper)
    if direct is not None:
        return direct
    legacy = LEGACY_TO_RISK.get(upper)
    if legacy is not None:
        return legacy
    raise ValueError(f"unknown alert level {value!r}")


def to_legacy(level: RiskLevel) -> LegacyLevel:
    return RISK_TO_LEGACY[coerce_level(level)]


def requires_approval(level: str) -> bool:
    resolved = coerce_level(level)
    if resolved == "GREY":
        return False
    return RISK_ORDER[resolved] > RISK_ORDER[AUTONOMOUS_RISK_CEILING]


def worst(levels: list[str]) -> RiskLevel:
    if not levels:
        return "GREY"
    return max((coerce_level(item) for item in levels), key=lambda item: RISK_ORDER[item])


def apply_hysteresis(previous: str | None, proposed: str, *, within_event: bool) -> RiskLevel:
    target = coerce_level(proposed)
    if previous is None:
        return target
    current = coerce_level(previous)
    if not within_event:
        return target
    if RISK_ORDER[target] >= RISK_ORDER[current]:
        return target
    return current
