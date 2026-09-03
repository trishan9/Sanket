from __future__ import annotations

import shutil
from pathlib import Path

from core.config import paths
from core.errors import RegistryError
from core.registry import LayerContract, load_all_contracts

NC_LICENSES = ("CC-BY-NC-4.0", "CC-BY-NC")


def is_noncommercial(contract: LayerContract) -> bool:
    return any(marker in contract.license for marker in NC_LICENSES)


def layer_readme(contract: LayerContract) -> str:
    lines = [
        f"# {contract.id}",
        "",
        f"**Source:** {contract.source_org}",
        f"**Licence:** {contract.license}",
        f"**Access:** {contract.access.kind}, refreshed {contract.access.refresh}",
        f"**Spatial:** {contract.spatial.crs}, {contract.spatial.resolution}",
        f"**Claim type:** {contract.claim_type}",
        f"**Confidence tier:** {contract.confidence_tier}",
        f"**Independence group:** `{contract.independence_group}`",
        "",
        "## Good for",
        *[f"- {item}" for item in contract.good_for],
        "",
        "## Cannot tell you",
        *[f"- {item}" for item in contract.cannot_tell_you],
        "",
    ]
    return "\n".join(lines)


def licence_table(contracts: dict[str, LayerContract]) -> str:
    rows = ["| Layer | Licence | Independence group | NC |", "|---|---|---|---|"]
    for contract in sorted(contracts.values(), key=lambda c: c.id):
        nc = "yes" if is_noncommercial(contract) else "no"
        rows.append(
            f"| {contract.id} | {contract.license} | `{contract.independence_group}` | {nc} |"
        )
    return "\n".join(rows)


def _link_layer(contract: LayerContract, destination: Path) -> None:
    silver_dir = paths.silver / contract.id
    if not silver_dir.exists():
        return
    target = destination / contract.id
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.mkdir(parents=True)
    for item in silver_dir.iterdir():
        (target / item.name).symlink_to(item.resolve())
    (target / "README.md").write_text(layer_readme(contract), encoding="utf-8")


def build_dataset_directory(output_dir: Path | None = None) -> Path:
    contracts = load_all_contracts()
    if not contracts:
        raise RegistryError("no registry contracts found; cannot publish an empty dataset")
    destination = output_dir or (paths.dist / "lakehouse")
    destination.mkdir(parents=True, exist_ok=True)
    nc_dir = destination / "nc"
    nc_dir.mkdir(exist_ok=True)
    for contract in contracts.values():
        target_root = nc_dir if is_noncommercial(contract) else destination
        _link_layer(contract, target_root)
    (destination / "LICENSES.md").write_text(licence_table(contracts), encoding="utf-8")
    return destination
