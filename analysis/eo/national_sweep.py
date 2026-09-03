from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from core.config import paths
from core.errors import RegistryError

HMAGLOFDB_PATH = paths.bronze / "hmaglofdb" / "HMAGLOFDB.csv"


@dataclass(frozen=True)
class BasinFeatures:
    gl_id: str
    country: str
    basin: str
    sub_basin: str
    rank: str
    area_km2: float
    elevation_m: float
    location: tuple[float, float]
    recurrence_count: int
    recurrence_countries_matched: bool


def _load_recurrence_counts() -> pd.Series:
    if not HMAGLOFDB_PATH.exists():
        raise RegistryError(f"HMAGLOFDB not found at {HMAGLOFDB_PATH}")
    df = pd.read_csv(HMAGLOFDB_PATH, low_memory=False, encoding="latin-1")
    counts: pd.Series = df.groupby("Country").size()
    return counts


def build_basin_features(pdgl: gpd.GeoDataFrame) -> list[BasinFeatures]:
    recurrence = _load_recurrence_counts()
    features = []
    for _, row in pdgl.iterrows():
        country = str(row["Country"])
        count = int(recurrence.get(country, 0))
        features.append(
            BasinFeatures(
                gl_id=str(row["GL_ID"]),
                country=country,
                basin=str(row["Basin"]),
                sub_basin=str(row["Sub_Basin"]),
                rank=str(row["Rank"]),
                area_km2=float(row["Area"]),
                elevation_m=float(row["Elevation"]),
                location=(float(row["Longitude"]), float(row["Latitude"])),
                recurrence_count=count,
                recurrence_countries_matched=count > 0,
            )
        )
    return features


def coarse_priority_score(feature: BasinFeatures) -> float:
    rank_weight = {"I": 3.0, "II": 2.0, "III": 1.0}.get(feature.rank, 1.0)
    area_component = min(feature.area_km2 / 2.0, 3.0)
    recurrence_component = min(feature.recurrence_count / 100.0, 2.0)
    return rank_weight + area_component + recurrence_component
