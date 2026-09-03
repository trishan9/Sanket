from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from analysis.hydro.scenarios import ScenarioKey, build_grid, load_scenario

MINUTES_PER_SECOND = 1.0 / 60.0


@dataclass(frozen=True)
class SettlementLeadTime:
    settlement: str
    chainage_m: float
    scenario: ScenarioKey
    lead_time_minutes: float | None


def _nearest_chainage(data_chainage: np.ndarray, target_chainage: float) -> int:
    return int(np.argmin(np.abs(data_chainage - target_chainage)))


def lead_time_for(
    settlement: str, settlement_chainage_m: float, scenario: ScenarioKey
) -> SettlementLeadTime:
    data = load_scenario(scenario.slug)
    chainage = data["chainage_m"]
    index = _nearest_chainage(chainage, settlement_chainage_m)
    arrival = data["arrival_time_s"][index]
    minutes = None if not np.isfinite(arrival) else float(arrival) * MINUTES_PER_SECOND
    return SettlementLeadTime(settlement, settlement_chainage_m, scenario, minutes)


def all_lead_times(
    settlement_chainages: dict[str, float],
    scenarios: list[ScenarioKey] | None = None,
) -> list[SettlementLeadTime]:
    scenarios = scenarios or build_grid()
    return [
        lead_time_for(name, chainage, scenario)
        for name, chainage in settlement_chainages.items()
        for scenario in scenarios
    ]


def minimum_lead_time(results: list[SettlementLeadTime], settlement: str) -> float | None:
    values = [
        r.lead_time_minutes
        for r in results
        if r.settlement == settlement and r.lead_time_minutes is not None
    ]
    return min(values) if values else None


def histogram(results: list[SettlementLeadTime], bins: int = 12) -> tuple[np.ndarray, np.ndarray]:
    values = np.array([r.lead_time_minutes for r in results if r.lead_time_minutes is not None])
    if values.size == 0:
        return np.array([]), np.array([])
    counts, edges = np.histogram(values, bins=bins)
    return counts, edges


def ecdf(results: list[SettlementLeadTime]) -> tuple[np.ndarray, np.ndarray]:
    values = np.sort(
        np.array([r.lead_time_minutes for r in results if r.lead_time_minutes is not None])
    )
    if values.size == 0:
        return np.array([]), np.array([])
    fraction = np.arange(1, len(values) + 1) / len(values)
    return values, fraction


def fraction_under_threshold(results: list[SettlementLeadTime], threshold_minutes: float) -> float:
    values = [r.lead_time_minutes for r in results if r.lead_time_minutes is not None]
    if not values:
        return 0.0
    return float(np.mean(np.array(values) < threshold_minutes))
