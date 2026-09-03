from __future__ import annotations

from datetime import date
from pathlib import Path

from core.connectors.base import FetchedFile, FetchManifest, bronze_dir, download, record
from core.connectors.clip import clip_local, clip_remote
from core.errors import ConnectorError

COG_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/cogs"
LICENSE = "public domain (UCSB Climate Hazards Center)"
SOURCE_ORG = "UCSB Climate Hazards Center, CHIRPS 2.0"


def cog_url(year: int, month: int) -> str:
    return f"{COG_BASE}/chirps-v2.0.{year}.{month:02d}.cog"


def fetch(
    years: range, months: tuple[int, ...], bbox: tuple[float, float, float, float]
) -> FetchManifest:
    target = bronze_dir("chirps")
    manifest = FetchManifest(
        dataset="chirps",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"{COG_BASE}, windowed COG clip to the corridor",
        independence_group="chirps_precipitation",
        claim_type="observation",
        notes=[
            "monthly 0.05 degree rainfall, clipped to the corridor",
            "used for the percentile rule-out against a 20-year climatology",
        ],
        cannot_tell_you=[
            "sub-daily rainfall intensity",
            "snowfall or snowmelt, which is what matters at these elevations",
            "rainfall at a point - it is a gridded satellite-gauge blend",
            "anything about a dry-day ice collapse, which is the point of the rule-out",
        ],
        bbox=bbox,
    )
    for year in years:
        for month in months:
            name = f"chirps-v2.0.{year}.{month:02d}.tif"
            out = target / name
            if out.exists():
                manifest.files.append(record(out, skipped=True))
                continue
            try:
                clip_remote(cog_url(year, month), bbox, out)
                manifest.files.append(record(out))
            except ConnectorError:
                manifest.notes.append(f"unavailable: {year}-{month:02d}")
    manifest.write()
    return manifest


PRELIM_DAILY = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_daily/tifs/p05"
FINAL_DAILY_COG = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/cogs/p05"


def daily_url(day: date, *, preliminary: bool) -> str:
    stem = f"chirps-v2.0.{day.year}.{day.month:02d}.{day.day:02d}"
    if preliminary:
        return f"{PRELIM_DAILY}/{day.year}/{stem}.tif.gz"
    return f"{FINAL_DAILY_COG}/{day.year}/{stem}.cog"


def clip_gzipped(url: str, bbox: tuple[float, float, float, float], out: Path) -> Path:
    import gzip
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "raw.tif.gz"
        download(url, archive, dataset="chirps_daily_prelim")
        expanded = Path(scratch) / "raw.tif"
        with gzip.open(archive, "rb") as source, expanded.open("wb") as target:
            shutil.copyfileobj(source, target)
        return clip_local(expanded, bbox, out)


def _daily_manifest(bbox: tuple[float, float, float, float], *, preliminary: bool) -> FetchManifest:
    notes = [
        "PRELIMINARY product - gauge-corrected final not yet published for this window"
        if preliminary
        else "final gauge-corrected daily product"
    ]
    cannot_tell_you = [
        "sub-daily intensity",
        "snowfall or snowmelt at these elevations",
        "a point measurement - it is a 0.05 degree gridded blend",
    ]
    if preliminary:
        cannot_tell_you.append("final values, which may revise once gauge data is incorporated")
    return FetchManifest(
        dataset="chirps_daily_prelim" if preliminary else "chirps_daily",
        source_org=SOURCE_ORG,
        license=LICENSE,
        access=f"{PRELIM_DAILY if preliminary else FINAL_DAILY_COG}, windowed clip",
        independence_group="chirps_precipitation",
        claim_type="observation",
        bbox=bbox,
        notes=notes,
        cannot_tell_you=cannot_tell_you,
    )


def _fetch_one_day(
    day: date, target: Path, bbox: tuple[float, float, float, float], *, preliminary: bool
) -> FetchedFile | None:
    out = target / f"chirps-{day.isoformat()}.tif"
    if out.exists():
        return record(out, skipped=True)
    url = daily_url(day, preliminary=preliminary)
    try:
        if preliminary:
            clip_gzipped(url, bbox, out)
        else:
            clip_remote(url, bbox, out)
        return record(out)
    except (ConnectorError, OSError):
        return None


def fetch_daily(
    days: list[date], bbox: tuple[float, float, float, float], *, preliminary: bool
) -> FetchManifest:
    target = bronze_dir("chirps_daily_prelim" if preliminary else "chirps_daily")
    manifest = _daily_manifest(bbox, preliminary=preliminary)
    for day in days:
        fetched = _fetch_one_day(day, target, bbox, preliminary=preliminary)
        if fetched is not None:
            manifest.files.append(fetched)
        else:
            manifest.notes.append(f"unavailable: {day.isoformat()}")
    manifest.write()
    return manifest
