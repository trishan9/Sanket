from __future__ import annotations

from datetime import date

import pytest

from analysis.met.anomaly import met_anomaly
from analysis.met.percentile import monthly_climatology, monthly_percentile
from analysis.met.ruleout import rainfall_explains
from core.errors import DetectionError

BHOTEKOSHI_2026 = date(2026, 8, 26)
MITERI_BRIDGE_2025 = date(2025, 7, 8)


def test_rainfall_does_not_explain_either_event_date() -> None:
    for target in (BHOTEKOSHI_2026, MITERI_BRIDGE_2025):
        result = rainfall_explains(target)
        assert result.explains is False, f"rainfall unexpectedly explained {target}"
        assert "does not explain" in result.rendered()


def test_july_2025_was_drier_than_the_median_month() -> None:
    observation = monthly_percentile(MITERI_BRIDGE_2025)
    assert observation.basin_mean_mm < observation.median_mm
    assert observation.percentile < 50.0
    assert observation.climatology_years >= 20


def test_climatology_spans_at_least_twenty_years() -> None:
    for month in (6, 7):
        series = monthly_climatology(month)
        assert len(series) >= 20


def test_unheld_layers_are_reported_as_unobserved_not_normal() -> None:
    anomaly = met_anomaly(BHOTEKOSHI_2026)
    assert "2 m air temperature" in anomaly.unobserved_layers
    assert "Not observed here" in anomaly.rendered()
    joined = " ".join(anomaly.notes).lower()
    assert "never as normal" in joined
    assert "conditioning factor, not a trigger" in joined


def test_antecedent_window_accumulates_real_rainfall() -> None:
    anomaly = met_anomaly(BHOTEKOSHI_2026)
    assert anomaly.antecedent_days == 7
    assert anomaly.antecedent_mm > 0.0


def test_missing_coverage_raises_rather_than_guessing() -> None:
    with pytest.raises(DetectionError):
        rainfall_explains(date(1990, 7, 1))
