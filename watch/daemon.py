from __future__ import annotations

import signal
import sys
import uuid
from datetime import UTC, datetime
from types import FrameType

import structlog
from apscheduler.schedulers.background import BackgroundScheduler

from agent.budget import budget
from agent.router import gateway
from agent.trace import Trace
from core.config import ensure_directories, settings
from core.corridor import Corridor, load_all_corridors
from core.state import State
from core.state import state as default_state
from watch import triggers
from watch.queue import recover_orphaned
from watch.tiers import RADAR_PRODUCT, handoff, run_tier1, run_tier2
from watch.worker import drain

log = structlog.get_logger()

WATCHED_FEATURE_ID = "lhende_barrier"
TIER0_PRODUCTS = ("OPERA_L3_DSWX-S1_V1", RADAR_PRODUCT)


def new_run_id() -> str:
    return uuid.uuid4().hex[:4]


def _run_tier1_and_beyond(corridor: Corridor, run_id: str, trace: Trace, store: State) -> str:
    for product in TIER0_PRODUCTS:
        tier1 = run_tier1(corridor, product, store=store)
        if tier1.signal is None:
            trace.watch(f"{product} baseline warming up on {tier1.tile}")
            continue
        trace.watch(
            f"{product} z={tier1.signal.z:.2f} vs 14-obs baseline on {tier1.tile} "
            f"-> {tier1.signal.classification}"
        )
        if not tier1.signal.outside_band:
            continue
        classification = run_tier2(tier1.signal, run_id, trace=trace)
        trace.watch(f"classify -> {classification}")
        if classification != "investigate":
            continue
        job_id, is_new = handoff(corridor, WATCHED_FEATURE_ID, tier1.signal, store=store)
        verb = "opened new" if is_new else "recognised existing"
        trace.emit("STEP", f"{verb} anomaly, queued investigation {job_id}", agent="watcher")
        return "escalated"
    return "quiet"


def tick(corridor: Corridor, store: State | None = None) -> dict[str, object]:
    target = store or default_state
    run_id = new_run_id()
    trace = Trace(run_id, corridor.basin_id, replay=corridor.mode == "replay")
    target.start_run(run_id, corridor.basin_id, "watcher", "scheduled")
    trace.trigger(f"scheduled tick · basin={corridor.basin_id} · run={run_id}")
    target.heartbeat(corridor.basin_id, "tick")

    result = triggers.tick(corridor, target)
    trace.watch(
        f"{sum(len(g.new_granule_ids) for g in result.granules)} new granules · "
        f"stage_breach={result.stage_breach} · anomalies_due={len(result.anomalies_due)}"
    )

    before = len(gateway.degradations)
    outcome = "quiet"
    if result.has_new_evidence or result.anomalies_due:
        outcome = _run_tier1_and_beyond(corridor, run_id, trace, target)

    processed = drain(corridor, target)
    if processed:
        outcome = "investigated"
        trace.watch(f"drained {len(processed)} queued investigation(s): {processed}")

    spent = budget.get(run_id)
    target.finish_run(
        run_id,
        steps=1,
        tokens_azure=spent.tokens_in.get("azure", 0),
        tokens_groq=spent.tokens_in.get("groq", 0),
        cost_npr=spent.total_npr,
        outcome=outcome,
        degradations=gateway.degradations[before:],
    )
    trace.done(f"tick complete · outcome={outcome}")
    return {"run_id": run_id, "outcome": outcome, "investigations": processed}


class Daemon:
    def __init__(self, fallback_interval_seconds: int = 900) -> None:
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._fallback_interval = fallback_interval_seconds
        self._corridors = load_all_corridors()
        self._stopping = False

    def _interval_for(self, basin_id: str) -> int:
        from agent.scout import cadence_seconds

        try:
            return cadence_seconds(basin_id)
        except Exception:
            return self._fallback_interval

    def start(self) -> None:
        ensure_directories()
        orphaned_runs = default_state.orphan_running_runs()
        orphaned_jobs = recover_orphaned()
        if orphaned_runs or orphaned_jobs:
            log.info(
                "recovered from crash", orphaned_runs=orphaned_runs, orphaned_jobs=orphaned_jobs
            )
        live_corridors = {k: c for k, c in self._corridors.items() if c.mode == "live"}
        for index, (key, corridor) in enumerate(live_corridors.items()):
            self._schedule(key, corridor, index)
        self._scheduler.start()
        log.info("daemon started", corridors=list(live_corridors))

    def _schedule(self, key: str, corridor: Corridor, index: int) -> None:
        self._scheduler.add_job(
            tick,
            "interval",
            seconds=self._interval_for(corridor.basin_id),
            args=[corridor],
            id=f"tick_{key}",
            next_run_time=datetime.now(UTC),
            jitter=index * 5,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    def retier(self, key: str) -> int:
        corridor = self._corridors[key]
        seconds = self._interval_for(corridor.basin_id)
        self._scheduler.reschedule_job(f"tick_{key}", trigger="interval", seconds=seconds)
        log.info("corridor retiered", corridor=key, interval_seconds=seconds)
        return seconds

    def stop(self, *_: object) -> None:
        if self._stopping:
            return
        self._stopping = True
        self._scheduler.shutdown(wait=False)
        log.info("daemon stopped")


def main() -> int:
    daemon = Daemon(fallback_interval_seconds=settings.tick_seconds_active)

    def handler(_signum: int, _frame: FrameType | None) -> None:
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    daemon.start()
    signal.pause()
    return 0
