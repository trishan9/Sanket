from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from analysis.eo.precip import percentile_for_date
from analysis.met.anomaly import MetAnomaly, met_anomaly
from analysis.met.percentile import MonthlyPercentile, monthly_percentile
from core.errors import DetectionError

EXTREME_DAILY_PERCENTILE = 90.0
EXTREME_MONTHLY_PERCENTILE = 90.0

RULEOUT_CAVEATS: tuple[str, ...] = (
    "a negative result: rainfall not being extreme does not identify what did cause an event",
    "CHIRPS is a satellite-gauge blend and can miss intense, highly localised convective cells",
    "the source catchment lies across the border with no ground gauges",
)


@dataclass(frozen=True)
class RainfallRuleOut:
    target_date: date
    explains: bool
    daily_percentile: float | None
    daily_mm: float | None
    monthly_percentile: float | None
    monthly_mm: float | None
    anomaly: MetAnomaly
    reason: str
    caveats: tuple[str, ...]

    def rendered(self) -> str:
        verdict = "rainfall is a plausible explanation" if self.explains else (
            "rainfall does not explain this event"
        )
        return f"{self.target_date.isoformat()}: {verdict}. {self.reason}"


def _daily(target: date) -> tuple[float | None, float | None]:
    try:
        observation = percentile_for_date(target)
    except (DetectionError, FileNotFoundError):
        return (None, None)
    return (observation.percentile_within_month, observation.basin_mean_mm)


def _monthly(target: date) -> tuple[float | None, float | None]:
    try:
        observation: MonthlyPercentile = monthly_percentile(target)
    except (DetectionError, FileNotFoundError):
        return (None, None)
    return (observation.percentile, observation.basin_mean_mm)


def rainfall_explains(target: date) -> RainfallRuleOut:
    daily_pct, daily_mm = _daily(target)
    monthly_pct, monthly_mm = _monthly(target)
    if daily_pct is None and monthly_pct is None:
        raise DetectionError(f"no CHIRPS coverage at any cadence for {target.isoformat()}")
    daily_extreme = daily_pct is not None and daily_pct >= EXTREME_DAILY_PERCENTILE
    monthly_extreme = monthly_pct is not None and monthly_pct >= EXTREME_MONTHLY_PERCENTILE
    explains = bool(daily_extreme or monthly_extreme)
    parts: list[str] = []
    if daily_pct is not None and daily_mm is not None:
        parts.append(f"daily basin rainfall {daily_mm:.1f} mm at the {daily_pct:.0f}th percentile")
    if monthly_pct is not None and monthly_mm is not None:
        parts.append(
            f"monthly basin total {monthly_mm:.1f} mm at the {monthly_pct:.0f}th percentile"
        )
    measured = "; ".join(parts)
    reason = (
        f"{measured}, at or above the {EXTREME_DAILY_PERCENTILE:.0f}th percentile threshold"
        if explains
        else f"{measured}, below the {EXTREME_DAILY_PERCENTILE:.0f}th percentile threshold "
        "this system uses to call rainfall a plausible driver"
    )
    return RainfallRuleOut(
        target_date=target,
        explains=explains,
        daily_percentile=daily_pct,
        daily_mm=daily_mm,
        monthly_percentile=monthly_pct,
        monthly_mm=monthly_mm,
        anomaly=met_anomaly(target),
        reason=reason,
        caveats=RULEOUT_CAVEATS,
    )
