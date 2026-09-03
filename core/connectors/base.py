from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from core.config import paths
from core.errors import ConnectorError

CHUNK = 1 << 20
TIMEOUT = 120.0


class FetchedFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: str
    bytes: int
    sha256: str
    skipped: bool = False


class FetchManifest(BaseModel):
    dataset: str
    source_org: str
    license: str
    access: str
    independence_group: str | None = None
    claim_type: str = "observation"
    bbox: tuple[float, float, float, float] | None = None
    temporal: tuple[str, str] | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    files: list[FetchedFile] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    cannot_tell_you: list[str] = Field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(f.bytes for f in self.files)

    def write(self) -> Path:
        paths.manifests.mkdir(parents=True, exist_ok=True)
        target = paths.manifests / f"{self.dataset}.json"
        target.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return target


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(dataset: str) -> FetchManifest | None:
    target = paths.manifests / f"{dataset}.json"
    if not target.exists():
        return None
    return FetchManifest(**json.loads(target.read_text(encoding="utf-8")))


def known_checksums(dataset: str) -> dict[str, str]:
    manifest = load_manifest(dataset)
    if manifest is None:
        return {}
    return {f.name: f.sha256 for f in manifest.files}


def record(path: Path, *, skipped: bool = False) -> FetchedFile:
    try:
        relative = str(path.relative_to(paths.root))
    except ValueError:
        relative = str(path)
    return FetchedFile(
        name=path.name,
        path=relative,
        bytes=path.stat().st_size,
        sha256=sha256_of(path),
        skipped=skipped,
    )


def download(
    url: str,
    target: Path,
    *,
    dataset: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> FetchedFile:
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = known_checksums(dataset).get(target.name)
    if target.exists() and expected and sha256_of(target) == expected:
        return record(target, skipped=True)
    try:
        with httpx.stream(
            "GET", url, timeout=TIMEOUT, follow_redirects=True, headers=headers, params=params
        ) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes(CHUNK):
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        raise ConnectorError(f"{dataset}: failed to fetch {url}: {exc}") from exc
    return record(target)


def get_json(
    url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
) -> Any:
    try:
        response = httpx.get(
            url, params=params, headers=headers, timeout=TIMEOUT, follow_redirects=True
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise ConnectorError(f"failed to fetch json from {url}: {exc}") from exc


def bronze_dir(name: str) -> Path:
    target = paths.bronze / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def as_of_guard(published: date | None, as_of: date) -> bool:
    return published is None or published <= as_of
