from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from core.config import paths
from core.errors import TemporalFirewallError
from core.registry import LayerContract, load_all_contracts

ACQUIRED_PATTERN = re.compile(r"_(\d{8})T\d{6}Z")
PUBLISHED_PATTERN = re.compile(r"_\d{8}T\d{6}Z_(\d{8})T\d{6}Z")
CHIRPS_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (
    dataset VARCHAR, file VARCHAR, path VARCHAR, bytes BIGINT,
    acquired_ts BIGINT, published_ts BIGINT,
    independence_group VARCHAR, claim_type VARCHAR,
    license VARCHAR, confidence_tier VARCHAR
)
"""


def _epoch(value: date | datetime) -> int:
    if isinstance(value, datetime):
        return int(value.replace(tzinfo=value.tzinfo or UTC).timestamp())
    return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())


def _dates_from_filename(name: str) -> tuple[int | None, int | None]:
    published_match = PUBLISHED_PATTERN.search(name)
    acquired_match = ACQUIRED_PATTERN.search(name)
    chirps_match = CHIRPS_PATTERN.search(name)
    acquired = None
    published = None
    if acquired_match:
        acquired = _epoch(datetime.strptime(acquired_match.group(1), "%Y%m%d"))
    if published_match:
        published = _epoch(datetime.strptime(published_match.group(1), "%Y%m%d"))
    elif chirps_match:
        acquired = _epoch(datetime.strptime(chirps_match.group(1), "%Y-%m-%d"))
        published = acquired
    if published is None:
        published = acquired
    return acquired, published


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, object]]
    rejected_count: int
    as_of: date


SOURCE_OVERRIDE: dict[str, str] = {"icimod_glacial_lakes": "manual/icimod"}


class Lakehouse:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or paths.lakehouse_db
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(self._path))
        self._connection.execute("INSTALL spatial; LOAD spatial;")
        self._connection.execute(_SCHEMA)

    def rebuild_catalog(self, contracts: dict[str, LayerContract] | None = None) -> int:
        contracts = contracts or load_all_contracts()
        self._connection.execute("DELETE FROM catalog")
        inserted = 0
        for dataset, contract in contracts.items():
            source = paths.bronze / SOURCE_OVERRIDE.get(dataset, dataset)
            if not source.exists():
                continue
            inserted += self._insert_dataset(dataset, contract, source)
        return inserted

    def _insert_dataset(self, dataset: str, contract: LayerContract, source: Path) -> int:
        rows = []
        for file_path in sorted(source.rglob("*")):
            if not file_path.is_file():
                continue
            acquired, published = _dates_from_filename(file_path.name)
            if acquired is None:
                acquired = _epoch(contract.temporal.published or date(2000, 1, 1))
            if published is None:
                published = acquired
            rows.append(
                (
                    dataset,
                    file_path.name,
                    str(file_path),
                    file_path.stat().st_size,
                    acquired,
                    published,
                    contract.independence_group,
                    contract.claim_type,
                    contract.license,
                    contract.confidence_tier,
                )
            )
        if rows:
            self._connection.executemany("INSERT INTO catalog VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        return len(rows)

    def query(self, sql: str, *, as_of: date, params: list[object] | None = None) -> QueryResult:
        cutoff = _epoch(as_of)
        firewalled = (
            f"WITH firewalled AS (  SELECT * FROM catalog WHERE published_ts <= {cutoff}) {sql}"
        )
        try:
            rows = self._connection.execute(firewalled, params or []).fetchdf().to_dict("records")
        except duckdb.Error as exc:
            raise TemporalFirewallError(f"lakehouse query failed: {exc}") from exc
        rejected = self._connection.execute(
            "SELECT count(*) FROM catalog WHERE published_ts > ?", [cutoff]
        ).fetchone()
        count = int(rejected[0]) if rejected else 0
        return QueryResult(rows=rows, rejected_count=count, as_of=as_of)

    def close(self) -> None:
        self._connection.close()


lakehouse = Lakehouse()
