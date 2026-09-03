from __future__ import annotations

from pathlib import Path

from core.config import paths
from core.connectors.base import FetchManifest, bronze_dir, download

RAW_BASE = "https://raw.githubusercontent.com/fidelsteiner/HMAGLOFDB/main"
FILES = ("Database/GLOFs/HMAGLOFDB.csv", "Database/GLOFs/HMAGLOFDB_removed.csv")
LICENSE = "CC-BY-4.0"
SOURCE_ORG = "Shrestha, Steiner et al. 2023, ESSD 15:3941"
ZENODO_DOI = "10.5281/zenodo.7271187"


def fetch() -> FetchManifest:
    target = bronze_dir("hmaglofdb")
    manifest = FetchManifest(
        dataset="hmaglofdb",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"github.com/fidelsteiner/HMAGLOFDB, Zenodo {ZENODO_DOI}",
        independence_group="hmaglofdb_record",
        claim_type="observation",
        notes=["697 GLOFs 1833-2022 at publication"],
        cannot_tell_you=[
            "events that were never reported - the record is documentary, not exhaustive",
            "whether GLOF frequency is increasing; the authors describe the evidence as ambiguous",
            "anything about lakes with no recorded outburst",
        ],
    )
    for name in FILES:
        try:
            manifest.files.append(
                download(f"{RAW_BASE}/{name}", target / Path(name).name, dataset="hmaglofdb")
            )
        except Exception as exc:
            manifest.notes.append(f"skipped {name}: {type(exc).__name__}")
    manifest.write()
    return manifest


def csv_path() -> Path:
    return paths.bronze / "hmaglofdb" / "HMAGLOFDB.csv"
