from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from core.config import paths
from core.errors import CorridorError

Coordinate = tuple[float, float]
BBox = tuple[float, float, float, float]


class WatchedFeature(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: str
    location: Coordinate
    pdgl: bool = False
    first_seen: date | None = None


class Settlement(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    location: Coordinate
    district: str


class SourceCatchment(BaseModel):
    model_config = ConfigDict(frozen=True)

    bbox: BBox
    country: str


class Authority(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: str
    body: str


class ReplaySpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    source: str
    clock_start: str
    clock_end: str
    speed: int = 3600
    as_of_follows_clock: bool = True


class Corridor(BaseModel):
    model_config = ConfigDict(frozen=True)

    basin_id: str
    name: str
    province: str
    districts: tuple[str, ...]
    bbox: BBox
    source_catchment: SourceCatchment
    watched_features: tuple[WatchedFeature, ...]
    downstream_reach: tuple[Settlement, ...]
    dem: str
    dem_vintage: date
    watched_products: tuple[str, ...]
    authority: Authority
    gauges: tuple[str, ...] = ()
    mode: Literal["live", "replay"] = "live"
    replay: ReplaySpec | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @property
    def settlement_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.downstream_reach)

    def feature(self, feature_id: str) -> WatchedFeature:
        for item in self.watched_features:
            if item.id == feature_id:
                return item
        raise CorridorError(f"no watched feature {feature_id} in {self.basin_id}")


def load_corridor(path: Path) -> Corridor:
    if not path.exists():
        raise CorridorError(f"corridor file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CorridorError(f"corridor file is not a mapping: {path}")
    try:
        return Corridor(**raw)
    except Exception as exc:
        raise CorridorError(f"invalid corridor {path.name}: {exc}") from exc


def load_all_corridors(directory: Path | None = None) -> dict[str, Corridor]:
    root = directory or paths.corridors
    corridors: dict[str, Corridor] = {}
    for path in sorted(root.glob("*.yml")):
        corridor = load_corridor(path)
        corridors[path.stem] = corridor
    return corridors
