from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import rasterio

from core.config import paths
from core.errors import DetectionError


@dataclass(frozen=True)
class PrecipObservation:
    target_date: date
    basin_mean_mm: float
    month_mean_mm: float
    percentile_within_month: float
    n_days_in_month: int
    source: str


def _basin_mean(path: str) -> float:
    with rasterio.open(path) as dataset:
        array = dataset.read(1).astype(float)
    valid = array[array >= 0]
    return float(valid.mean()) if valid.size else float("nan")


def daily_series_for_month(year: int, month: int) -> dict[date, float]:
    directory = paths.bronze / "chirps_daily_prelim"
    pattern = f"chirps-{year:04d}-{month:02d}-*.tif"
    series: dict[date, float] = {}
    for path in sorted(directory.glob(pattern)):
        stem = path.stem.rsplit("chirps-", 1)[-1]
        day = date.fromisoformat(stem)
        series[day] = _basin_mean(str(path))
    return series


def percentile_for_date(target_date: date) -> PrecipObservation:
    series = daily_series_for_month(target_date.year, target_date.month)
    if target_date not in series:
        raise DetectionError(f"no CHIRPS daily observation for {target_date.isoformat()}")
    values = np.array(list(series.values()))
    value = series[target_date]
    percentile = float((values < value).mean() * 100)
    return PrecipObservation(
        target_date=target_date,
        basin_mean_mm=value,
        month_mean_mm=float(values.mean()),
        percentile_within_month=percentile,
        n_days_in_month=len(series),
        source="CHIRPS preliminary daily",
    )
