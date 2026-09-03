from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from core.connectors import dhm
from core.connectors.opera import search
from core.corridor import Corridor
from core.errors import ConnectorError
from core.state import State, now_iso
from core.state import state as default_state

GRANULE_LOOKBACK_DAYS_ON_COLD_START = 730


@dataclass(frozen=True)
class GranuleCheck:
    product: str
    new_granule_ids: tuple[str, ...]
    checked_from: datetime | None
    checked_at: datetime


@dataclass(frozen=True)
class TickResult:
    basin_id: str
    granules: tuple[GranuleCheck, ...]
    stage_breach: bool
    anomalies_due: tuple[str, ...]

    @property
    def has_new_evidence(self) -> bool:
        return any(g.new_granule_ids for g in self.granules) or self.stage_breach


def _last_granule_check(basin_id: str, product: str, store: State) -> datetime | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT last_checked FROM granule_checks WHERE basin_id=? AND product=?",
            (basin_id, product),
        ).fetchone()
    return datetime.fromisoformat(row["last_checked"]) if row else None


def _record_granule_check(basin_id: str, product: str, store: State) -> None:
    with store._lock, store.connect() as connection:
        connection.execute(
            "INSERT INTO granule_checks (basin_id, product, last_checked) VALUES (?,?,?) "
            "ON CONFLICT(basin_id, product) DO UPDATE SET last_checked=excluded.last_checked",
            (basin_id, product, now_iso()),
        )


def check_granules(corridor: Corridor, store: State | None = None) -> tuple[GranuleCheck, ...]:
    target = store or default_state
    checks = []
    for product in corridor.watched_products:
        if not product.startswith("OPERA"):
            continue
        since = _last_granule_check(corridor.basin_id, product, target)
        temporal = (since.date().isoformat(), date.today().isoformat()) if since else None
        try:
            results = search(product, corridor.bbox, temporal)
            ids = tuple(str(g.get("meta", {}).get("concept-id", i)) for i, g in enumerate(results))
        except ConnectorError:
            ids = ()
        checks.append(GranuleCheck(product, ids, since, datetime.now(UTC)))
        _record_granule_check(corridor.basin_id, product, target)
    return tuple(checks)


def check_stage(corridor: Corridor) -> bool:
    for gauge in corridor.gauges:
        try:
            if dhm.stage_above_threshold(gauge):
                return True
        except ConnectorError:
            continue
    return False


def anomalies_due(basin_id: str, store: State | None = None) -> tuple[str, ...]:
    target = store or default_state
    now = now_iso()
    with target.connect() as connection:
        rows = connection.execute(
            "SELECT anomaly_id FROM anomalies WHERE basin_id=? AND status='open' "
            "AND (next_recheck IS NULL OR next_recheck <= ?)",
            (basin_id, now),
        ).fetchall()
    return tuple(row["anomaly_id"] for row in rows)


def tick(corridor: Corridor, store: State | None = None) -> TickResult:
    target = store or default_state
    granules = check_granules(corridor, target)
    stage_breach = check_stage(corridor)
    due = anomalies_due(corridor.basin_id, target)
    return TickResult(corridor.basin_id, granules, stage_breach, due)
