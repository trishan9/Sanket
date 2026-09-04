from __future__ import annotations

import inspect
from datetime import date

from core.lakehouse import Lakehouse
from core.registry import load_all_contracts


def test_every_silver_layer_has_a_validated_contract() -> None:
    contracts = load_all_contracts()
    assert len(contracts) >= 12
    for contract in contracts.values():
        assert contract.cannot_tell_you
        assert contract.good_for
        assert contract.independence_group


def test_as_of_firewall_excludes_and_counts_post_cutoff_rows(tmp_path) -> None:
    lakehouse = Lakehouse(tmp_path / "test.duckdb")
    lakehouse.rebuild_catalog()

    full = lakehouse.query("SELECT count(*) AS n FROM firewalled", as_of=date(2026, 9, 3))
    assert full.rejected_count == 0

    narrowed = lakehouse.query("SELECT count(*) AS n FROM firewalled", as_of=date(2026, 6, 1))
    assert narrowed.rejected_count > 0
    assert narrowed.rows[0]["n"] < full.rows[0]["n"]
    lakehouse.close()


def test_admin_boundaries_never_reach_a_scoring_function() -> None:
    from analysis.hydro import stage_volume

    source = inspect.getsource(stage_volume)
    forbidden = ("adm0", "adm1", "adm2", "district", "province", "country_boundary")
    lowered = source.lower()
    for term in forbidden:
        assert term not in lowered, f"scoring module references admin geometry: {term}"


def test_second_corridor_loads_with_no_code_change() -> None:
    from core.corridor import load_all_corridors

    corridors = load_all_corridors()
    assert len(corridors) >= 2
    assert "thame" in corridors
    assert corridors["thame"].authority.body == "DDMC Solukhumbu"


def test_publish_produces_a_valid_dataset_directory(tmp_path) -> None:
    from core.publish import build_dataset_directory

    destination = build_dataset_directory(tmp_path / "lakehouse")
    assert (destination / "LICENSES.md").exists()
    layer_dirs = [p for p in destination.iterdir() if p.is_dir() and p.name != "nc"]
    assert len(layer_dirs) >= 8
    for layer in layer_dirs:
        assert (layer / "README.md").exists()
