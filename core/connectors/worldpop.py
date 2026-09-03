from __future__ import annotations

import tempfile
from pathlib import Path

from core.connectors.base import FetchManifest, bronze_dir, download, record
from core.connectors.clip import clip_local
from core.errors import ConnectorError

BASE = "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM"
LICENSE = "CC-BY-4.0"
SOURCE_ORG = "WorldPop, University of Southampton"


def url(iso3: str = "NPL", year: int = 2020) -> str:
    return f"{BASE}/{iso3}/{iso3.lower()}_ppp_{year}_UNadj_constrained.tif"


def fetch(
    bbox: tuple[float, float, float, float], *, iso3: str = "NPL", year: int = 2020
) -> FetchManifest:
    target = bronze_dir("worldpop")
    manifest = FetchManifest(
        dataset="worldpop",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"{BASE}/{iso3}, windowed COG clip",
        independence_group="worldpop_population",
        claim_type="model_output",
        bbox=bbox,
        notes=[f"constrained UN-adjusted {year} population, 100 m"],
        cannot_tell_you=[
            "who was actually present - it models usual residence",
            "displacement after 26 August 2026",
            "anything at building resolution; counts are order-of-magnitude",
            f"population change since {year}",
        ],
    )
    out = target / f"{iso3.lower()}_ppp_{year}_constrained.tif"
    if out.exists():
        manifest.files.append(record(out, skipped=True))
    else:
        try:
            with tempfile.TemporaryDirectory() as scratch:
                whole = Path(scratch) / "national.tif"
                download(url(iso3, year), whole, dataset="worldpop")
                clip_local(whole, bbox, out)
            manifest.files.append(record(out))
            manifest.notes.append(
                "national raster downloaded, then clipped locally: "
                "the WorldPop server does not support range requests"
            )
        except (ConnectorError, OSError) as exc:
            manifest.notes.append(f"unavailable: {exc}")
    manifest.write()
    return manifest
