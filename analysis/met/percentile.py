from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import numpy as np
import rasterio

from core.config import paths
from core.errors import DetectionError

MONTHLY_DIRECTORY = paths.bronze / "chirps"
MONTHLY_PATTERN = re.compile(r"chirps-v2\.0\.(\d{4})\.(\d{2})\.tif$")
CLIMATOLOGY_SOURCE = "CHIRPS v2.0 monthly, UCSB Climate Hazards Center"


@dataclass(frozen=True)
class MonthlyPercentile:
    target_month: str
    basin_mean_mm: float
    climatology_years: int
    percentile: float
    rank: int
    median_mm: float
    source: str

    def rendered(self) -> str:
        return (
            f"{self.target_month}: basin mean {self.basin_mean_mm:.1f} mm, "
            f"{self.percentile:.0f}th percentile against {self.climatology_years} same-month "
            f"years (median {self.median_mm:.1f} mm), {self.source}"
        )


def _basin_mean(path: str) -> float:
    with rasterio.open(path) as dataset:
        array = dataset.read(1).astype(float)
    valid = array[array >= 0]
    return float(valid.mean()) if valid.size else float("nan")


@lru_cache(maxsize=8)
def monthly_climatology(month: int) -> dict[int, float]:
    series: dict[int, float] = {}
    for path in sorted(MONTHLY_DIRECTORY.glob("*.tif")):
        match = MONTHLY_PATTERN.search(path.name)
        if match is None or int(match.group(2)) != month:
            continue
        series[int(match.group(1))] = _basin_mean(str(path))
    return series


def monthly_percentile(target: date) -> MonthlyPercentile:
    series = monthly_climatology(target.month)
    if target.year not in series:
        raise DetectionError(
            f"no CHIRPS monthly grid for {target.year}-{target.month:02d}; "
            "cannot place it against the climatology"
        )
    value = series[target.year]
    others = np.array([v for year, v in series.items() if np.isfinite(v)])
    percentile = float((others < value).mean() * 100)
    ordered = sorted(others, reverse=True)
    return MonthlyPercentile(
        target_month=f"{target.year}-{target.month:02d}",
        basin_mean_mm=value,
        climatology_years=len(others),
        percentile=percentile,
        rank=int(ordered.index(value) + 1) if value in ordered else len(ordered),
        median_mm=float(np.median(others)),
        source=CLIMATOLOGY_SOURCE,
    )
