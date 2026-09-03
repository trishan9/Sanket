from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from core.config import paths
from core.errors import RegistryError
from core.provenance import ClaimType

AccessKind = Literal["earthaccess", "stac", "hdx", "manual", "github", "http"]
ConfidenceTier = Literal["high", "medium", "low"]


class AccessSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: AccessKind
    dataset: str
    refresh: str = "static"
    checksum: str = "sha256"


class SpatialSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    crs: str
    extent: tuple[float, float, float, float]
    resolution: str


class TemporalSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    observed: date | None = None
    published: date | None = None


class LayerContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_org: str
    access: AccessSpec
    license: str
    spatial: SpatialSpec
    temporal: TemporalSpec
    claim_type: ClaimType
    confidence_tier: ConfidenceTier
    good_for: tuple[str, ...] = Field(min_length=1)
    cannot_tell_you: tuple[str, ...] = Field(min_length=1)
    independence_group: str


def load_contract(path: Path) -> LayerContract:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryError(f"contract is not a mapping: {path}")
    try:
        return LayerContract(**raw)
    except Exception as exc:
        raise RegistryError(f"invalid contract {path.name}: {exc}") from exc


def load_all_contracts(directory: Path | None = None) -> dict[str, LayerContract]:
    root = directory or paths.registry
    contracts: dict[str, LayerContract] = {}
    for path in sorted(root.glob("*.yml")):
        contract = load_contract(path)
        if contract.id in contracts:
            raise RegistryError(f"duplicate contract id {contract.id}")
        contracts[contract.id] = contract
    return contracts


def independence_groups(contracts: dict[str, LayerContract]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for contract in contracts.values():
        grouped.setdefault(contract.independence_group, []).append(contract.id)
    return {group: tuple(ids) for group, ids in grouped.items()}
