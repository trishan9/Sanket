from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from analysis.eo.baselines import Baseline
from core.config import settings

Classification = Literal["within_band", "escalation", "de_escalation"]


@dataclass(frozen=True)
class ChangeSignal:
    observed: float
    baseline: Baseline
    z: float
    classification: Classification

    @property
    def outside_band(self) -> bool:
        return self.classification != "within_band"


def classify(observed: float, baseline: Baseline) -> ChangeSignal:
    z = baseline.z_score(observed)
    if z >= settings.escalation_z:
        classification: Classification = "escalation"
    elif z <= -settings.escalation_z:
        classification = "de_escalation"
    else:
        classification = "within_band"
    return ChangeSignal(observed=observed, baseline=baseline, z=z, classification=classification)


def update_baseline_values(history: list[float], observed: float) -> list[float]:
    updated = [*history, observed]
    return updated[-settings.baseline_observations :]
