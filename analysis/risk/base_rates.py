from __future__ import annotations

import math
from functools import lru_cache

import geopandas as gpd
import pandas as pd

from analysis.risk.schemas import BaseRate, DamType
from core.config import paths

HMAGLOFDB_CSV = paths.bronze / "hmaglofdb" / "HMAGLOFDB.csv"
INVENTORY_PARQUET = paths.silver / "icimod_glacial_lakes" / "glacial_lakes_2015.parquet"
PDGL_PARQUET = paths.silver / "icimod_glacial_lakes" / "pdgl.parquet"

RECORD_PERIOD = "1833-2022 documentary record"

LAKE_TYPE_TO_DAM: dict[str, DamType] = {
    "Moraine dammed": "moraine",
    "Ice dammed": "ice",
    "Supraglacial": "ice",
    "Bedrock": "bedrock",
    "Landslide dammed": "landslide_debris",
    "Thermokarst": "moraine",
    "Water pocket": "ice",
}

INVENTORY_TYPE_TO_DAM: dict[str, DamType] = {
    "M(o)": "moraine",
    "M(e)": "moraine",
    "M(l)": "moraine",
    "I(s)": "ice",
    "I(v)": "ice",
    "E(o)": "bedrock",
    "E(c)": "bedrock",
    "O": "unknown",
}

RATE_CAVEAT = (
    "an events-per-inventoried-lake rate over an incomplete documentary record, not a "
    "probability that any particular lake will fail and not a forecast of when"
)


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 0.0)
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    centre = proportion + z * z / (2 * trials)
    spread = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials))
    return (
        max(0.0, (centre - spread) / denominator),
        min(1.0, (centre + spread) / denominator),
    )


def poisson_rate_interval(events: int, exposure: int, alpha: float = 0.05) -> tuple[float, float]:
    from scipy import stats

    if exposure <= 0:
        return (0.0, 0.0)
    low = 0.0 if events == 0 else float(stats.chi2.ppf(alpha / 2, 2 * events) / 2.0)
    high = float(stats.chi2.ppf(1 - alpha / 2, 2 * events + 2) / 2.0)
    return (low / exposure, high / exposure)


@lru_cache(maxsize=1)
def _events() -> pd.DataFrame:
    frame = pd.read_csv(HMAGLOFDB_CSV, low_memory=False, encoding="latin-1")
    frame["dam_type"] = frame["Lake_type"].map(LAKE_TYPE_TO_DAM).fillna("unknown")
    return frame


@lru_cache(maxsize=1)
def _inventory() -> gpd.GeoDataFrame:
    frame = gpd.read_parquet(INVENTORY_PARQUET)
    frame["dam_type"] = frame["Type"].map(INVENTORY_TYPE_TO_DAM).fillna("unknown")
    return frame


@lru_cache(maxsize=1)
def pdgl_inventory() -> gpd.GeoDataFrame:
    return gpd.read_parquet(PDGL_PARQUET)


@lru_cache(maxsize=1)
def base_rate_by_dam_type() -> dict[DamType, BaseRate]:
    events = _events()["dam_type"].value_counts().to_dict()
    population = _inventory()["dam_type"].value_counts().to_dict()
    rates: dict[DamType, BaseRate] = {}
    for dam_type, lakes in population.items():
        if dam_type == "unknown":
            continue
        count = int(events.get(dam_type, 0))
        total = int(lakes)
        low, high = poisson_rate_interval(count, total)
        rate = count / total if total else 0.0
        caveat = RATE_CAVEAT
        if rate > 1.0:
            caveat = (
                f"{RATE_CAVEAT}; exceeds one event per lake because {dam_type}-dammed lakes "
                "drain and refill repeatedly, so this counts recurrent events rather than "
                "the share of lakes that have ever failed"
            )
        rates[dam_type] = BaseRate(
            stratum=f"{dam_type}-dammed",
            events=count,
            population=total,
            rate_per_lake=rate,
            ci_low=low,
            ci_high=high,
            sample_size=total,
            record_period=RECORD_PERIOD,
            caveat=caveat,
        )
    return rates


def rate_for(dam_type: DamType) -> BaseRate | None:
    return base_rate_by_dam_type().get(dam_type)


def relative_dam_weight(dam_type: DamType) -> float:
    rates = base_rate_by_dam_type()
    if not rates:
        return 0.5
    values = {key: value.rate_per_lake for key, value in rates.items()}
    ceiling = max(values.values()) or 1.0
    return min(1.0, values.get(dam_type, 0.0) / ceiling)


def country_event_counts() -> dict[str, int]:
    return {str(k): int(v) for k, v in _events()["Country"].value_counts().items()}
