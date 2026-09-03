from __future__ import annotations

import hashlib
import re
from datetime import date

import pandas as pd

from agent.rag.store import Chunk, upsert
from core.connectors.hmaglofdb import csv_path
from core.registry import LayerContract, load_all_contracts

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s,;]+")


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(parts)
    return f"{prefix}-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _doi_url(reference: str) -> str:
    match = DOI_PATTERN.search(reference)
    return f"https://doi.org/{match.group(0)}" if match else "https://essd.copernicus.org"


def _event_year(row: pd.Series) -> int:
    exact = row.get("Year_exact")
    if pd.notna(exact):
        return int(exact)
    approx = row.get("Year_approx")
    if pd.notna(approx):
        digits = re.search(r"\d{4}", str(approx))
        if digits:
            return int(digits.group(0))
    return 2000


def _cell(row: pd.Series, key: str, default: str) -> str:
    value = row.get(key)
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text or default


def _hmaglofdb_text(row: pd.Series) -> str:
    lake = _cell(row, "Lake_name", "unnamed lake")
    glacier = _cell(row, "Glacier_name", "unnamed glacier")
    country = _cell(row, "Country", "unknown country")
    basin = _cell(row, "River_Basin", "unknown basin")
    parts = [
        f"{lake} on the {glacier} in {country}, {basin} basin.",
        f"Lake type: {_cell(row, 'Lake_type', 'unknown')}.",
        f"GLOF driver: {_cell(row, 'Driver_GLOF', 'unknown')}.",
        f"Mechanism: {_cell(row, 'Mechanism', 'unknown')}.",
    ]
    impact = _cell(row, "Impact", "")
    if impact:
        parts.append(f"Impact: {impact}.")
    return " ".join(parts)


def ingest_hmaglofdb_science(*, limit: int = 60) -> int:
    frame = pd.read_csv(csv_path(), low_memory=False, encoding="latin-1")
    frame = frame[frame["Ref_scientific_full"].notna()]
    frame = frame.sort_values("Country", key=lambda c: c != "Nepal")
    chunks: list[Chunk] = []
    for _, row in frame.head(limit).iterrows():
        reference = str(row["Ref_scientific_full"])
        year = _event_year(row)
        chunks.append(
            Chunk(
                id=_stable_id("hmaglofdb", str(row["GF_ID"]), reference[:40]),
                text=f"{_hmaglofdb_text(row)} Source: {reference}",
                source_org="HMAGLOFDB (Shrestha, Steiner et al. 2023, ESSD 15:3941)",
                url=_doi_url(reference),
                published_at=date(min(year, 2023), 1, 1),
                claim_type="official",
                independence_group="hmaglofdb_record",
                geo=str(row.get("Country", "unknown")),
            )
        )
    return upsert("science", chunks)


def _registry_text(contract: LayerContract) -> str:
    good_for = "; ".join(contract.good_for)
    cannot = "; ".join(contract.cannot_tell_you)
    return (
        f"{contract.id} ({contract.source_org}, {contract.confidence_tier} confidence tier). "
        f"Good for: {good_for}. Cannot tell you: {cannot}."
    )


def ingest_registry_science() -> int:
    contracts = load_all_contracts()
    chunks = [
        Chunk(
            id=_stable_id("registry", contract.id),
            text=_registry_text(contract),
            source_org=contract.source_org,
            url=f"registry://{contract.id}",
            published_at=contract.temporal.published or date(2020, 1, 1),
            claim_type="official",
            independence_group=contract.independence_group,
            geo="nepal",
        )
        for contract in contracts.values()
    ]
    return upsert("science", chunks)


LHENDE_EVENTS: tuple[Chunk, ...] = (
    Chunk(
        id="lhende-dhm-attribution-2026-08-28",
        text=(
            "DHM's review of satellite imagery over the Lhende barrier attributes the 26 "
            "August 2026 event to a supraglacial lake outburst flood. The assessment is based "
            "on optical and radar scenes supplied by the same regional partner imagery feed "
            "used for the upstream catchment."
        ),
        source_org="Department of Hydrology and Meteorology (DHM), Nepal",
        url="https://dhm.gov.np",
        published_at=date(2026, 8, 28),
        claim_type="official",
        independence_group="dhm_icimod_imagery",
        geo="lhende",
    ),
    Chunk(
        id="lhende-icimod-attribution-2026-08-28",
        text=(
            "ICIMOD's cross-check of the same imagery feed concurs with DHM: the 26 August "
            "2026 Lhende event is consistent with a supraglacial lake outburst. No independent "
            "imagery source was used for this cross-check."
        ),
        source_org="ICIMOD",
        url="https://icimod.org",
        published_at=date(2026, 8, 28),
        claim_type="official",
        independence_group="dhm_icimod_imagery",
        geo="lhende",
    ),
    Chunk(
        id="lhende-geopera-reconstruction-2026-08-29",
        text=(
            "geo-pera's independent stereo-elevation reconstruction of the Lhende barrier, "
            "built from a separate commercial tasking order, found no pre-existing supraglacial "
            "lake basin was drained. The observed elevation change does not match a lake-"
            "outburst source geometry."
        ),
        source_org="geo-pera (bhotekoshi-2026-reconstruction)",
        url="https://github.com/geo-pera/bhotekoshi-2026-reconstruction",
        published_at=date(2026, 8, 29),
        claim_type="analysis",
        independence_group="geo_pera_analysis",
        geo="lhende",
    ),
    Chunk(
        id="lhende-geopera-retraction-2026-08-31",
        text=(
            "geo-pera publicly retracted its initial sediment-volume estimate for the Lhende "
            "event after identifying a parallax error in its DEM differencing pipeline. The "
            "retraction concerns the volume figure only; the separate finding that no pre-"
            "existing lake basin was drained is unaffected and was not retracted."
        ),
        source_org="geo-pera (bhotekoshi-2026-reconstruction)",
        url="https://github.com/geo-pera/bhotekoshi-2026-reconstruction",
        published_at=date(2026, 8, 31),
        claim_type="retracted",
        independence_group="geo_pera_analysis",
        geo="lhende",
    ),
)


def ingest_events() -> int:
    return upsert("events", list(LHENDE_EVENTS))


def ingest_all() -> dict[str, int]:
    return {
        "science_hmaglofdb": ingest_hmaglofdb_science(),
        "science_registry": ingest_registry_science(),
        "events": ingest_events(),
    }
