from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from analysis.eo.precip import daily_series_for_month
from analysis.met.percentile import monthly_climatology

ANTECEDENT_DAYS = 7

UNHELD_LAYERS: tuple[str, ...] = (
    "2 m air temperature",
    "freezing level height",
    "snowmelt flux",
)

TEMPERATURE_NOTE = (
    "temperature is a conditioning factor, not a trigger: the peer-reviewed Thame "
    "reconstruction links a temperature spike to the tipping point but does not make it "
    "causal on its own"
)


@dataclass(frozen=True)
class MetAnomaly:
    target_date: date
    antecedent_mm: float
    antecedent_days: int
    seasonal_context: str
    unobserved_layers: tuple[str, ...]
    notes: tuple[str, ...]

    def rendered(self) -> str:
        return (
            f"{self.target_date.isoformat()}: {self.antecedent_mm:.1f} mm over the previous "
            f"{self.antecedent_days} days. {self.seasonal_context}. Not observed here: "
            f"{', '.join(self.unobserved_layers)}."
        )


def antecedent_rainfall(target: date, days: int = ANTECEDENT_DAYS) -> float:
    total = 0.0
    for offset in range(1, days + 1):
        day = target - timedelta(days=offset)
        series = daily_series_for_month(day.year, day.month)
        total += series.get(day, 0.0)
    return total


def _seasonal_context(target: date) -> str:
    climatology = monthly_climatology(target.month)
    if not climatology:
        return "no same-month climatology is held for this basin"
    values = sorted(climatology.values())
    median = values[len(values) // 2]
    return (
        f"month {target.month:02d} carries a {median:.0f} mm median basin total across "
        f"{len(values)} years, so this is monsoon season and wet ground is the norm"
    )


def met_anomaly(target: date) -> MetAnomaly:
    return MetAnomaly(
        target_date=target,
        antecedent_mm=antecedent_rainfall(target),
        antecedent_days=ANTECEDENT_DAYS,
        seasonal_context=_seasonal_context(target),
        unobserved_layers=UNHELD_LAYERS,
        notes=(
            TEMPERATURE_NOTE,
            "layers this system does not hold are reported as not observed, never as normal",
        ),
    )
