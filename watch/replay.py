from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from actions.pipeline import run_verifier_explainer_actor
from agent.loop import investigate
from agent.trace import Trace
from core.config import paths
from core.connectors.base import FetchManifest, record
from core.corridor import Corridor
from core.errors import ConfigError
from core.state import State
from core.state import state as default_state
from watch.tiers import RADAR_PRODUCT, handoff, run_tier1, run_tier2

REPLAY_TILE = "T45RUL"
REPLAY_DATASET = "bhotekoshi_2026_08"
DIST_DATE = re.compile(r"_(\d{8})T\d{6}Z_")
DSWX_DATE = re.compile(r"_(\d{8})T\d{6}Z_")
RTC_DATE = re.compile(r"_(\d{8})T\d{6}_")


def _within_cutoff(name: str, pattern: re.Pattern[str], cutoff: date) -> bool:
    match = pattern.search(name)
    if match is None:
        return False
    return datetime.strptime(match.group(1), "%Y%m%d").date() <= cutoff


def _replay_sources(cutoff: date) -> list[Path]:
    sources: list[Path] = []
    dist_dir = paths.bronze / "opera_l3_dist_alert_hls_v1"
    sources += [
        p
        for p in sorted(dist_dir.glob(f"*{REPLAY_TILE}*.tif"))
        if _within_cutoff(p.name, DIST_DATE, cutoff)
    ]
    dswx_dir = paths.bronze / "opera_l3_dswx_s1_v1"
    sources += [
        p
        for p in sorted(dswx_dir.glob(f"*{REPLAY_TILE}*.tif"))
        if _within_cutoff(p.name, DSWX_DATE, cutoff)
    ]
    rtc_dir = paths.bronze / "sentinel_1_rtc"
    sources += [
        p for p in sorted(rtc_dir.glob("*_vv.tif")) if _within_cutoff(p.name, RTC_DATE, cutoff)
    ]
    return sources


def build_replay_snapshot(cutoff: date) -> FetchManifest:
    target_dir = paths.replay / REPLAY_DATASET
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = FetchManifest(
        dataset=REPLAY_DATASET,
        source_org="NASA/JPL OPERA; ESA Copernicus Sentinel-1 via Planetary Computer",
        license="public domain (NASA) / Copernicus open data",
        access="symlinked from data/bronze; every file was acquired on or before the replay cutoff",
        temporal=("2026-08-27", cutoff.isoformat()),
    )
    for source in _replay_sources(cutoff):
        link = target_dir / source.name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(source.resolve())
        manifest.files.append(record(source))
    manifest.write()
    return manifest


def verify_replay_checksums(manifest: FetchManifest) -> list[str]:
    from core.connectors.base import sha256_of

    mismatches: list[str] = []
    for entry in manifest.files:
        actual_path = paths.root / entry.path
        if not actual_path.exists():
            mismatches.append(f"{entry.path}: missing")
            continue
        actual_hash = sha256_of(actual_path)
        if actual_hash != entry.sha256:
            mismatches.append(f"{entry.path}: {actual_hash} != {entry.sha256}")
    return mismatches


@dataclass(frozen=True)
class ReplayClock:
    clock_start: datetime
    clock_end: datetime
    speed: float
    real_start: datetime

    def simulated_now(self) -> datetime:
        elapsed_real = (datetime.now(UTC) - self.real_start).total_seconds()
        simulated = self.clock_start + timedelta(seconds=elapsed_real * self.speed)
        return min(simulated, self.clock_end)

    def as_of(self) -> date:
        return self.simulated_now().date()

    def finished(self) -> bool:
        return self.simulated_now() >= self.clock_end


def build_clock(corridor: Corridor) -> ReplayClock:
    spec = corridor.replay
    if spec is None:
        raise ConfigError(f"corridor {corridor.basin_id} has no replay spec")
    return ReplayClock(
        clock_start=datetime.fromisoformat(spec.clock_start),
        clock_end=datetime.fromisoformat(spec.clock_end),
        speed=float(spec.speed),
        real_start=datetime.now(UTC),
    )


def _features_newly_due(corridor: Corridor, as_of: date, previous: date | None) -> list[str]:
    due = []
    for feature in corridor.watched_features:
        if feature.first_seen is None or feature.first_seen > as_of:
            continue
        if previous is not None and feature.first_seen <= previous:
            continue
        due.append(feature.id)
    return due


@dataclass(frozen=True)
class ReplayTick:
    simulated_time: datetime
    as_of: date
    outcome: str
    run_id: str | None


@dataclass(frozen=True)
class ReplaySummary:
    ticks: tuple[ReplayTick, ...]
    tool_sequences: tuple[tuple[str, ...], ...]


def _investigate_feature(
    corridor: Corridor,
    feature_id: str,
    run_prefix: str,
    as_of: date,
    store: State,
    deterministic: bool = False,
) -> tuple[str, tuple[str, ...]]:
    run_id = f"{run_prefix}_{feature_id}_{as_of.isoformat()}"
    trace = Trace(run_id, corridor.basin_id, replay=True)
    trace.trigger(f"replay: watched feature {feature_id} first_seen reached at {as_of}")
    ledger = investigate(
        corridor,
        f"replay_{feature_id}",
        feature_id,
        {"source": "replay first_seen", "as_of": as_of.isoformat()},
        run_id,
        trace,
        store=store,
        as_of=as_of,
        deterministic=deterministic,
    )
    tools = tuple(line.tool for line in trace.lines if line.kind == "TOOL" and line.tool)
    trace.done(f"replay investigation concluded: {ledger.outcome}")
    run_verifier_explainer_actor(corridor, ledger, run_id, trace, store, replay=True)
    return run_id, tools


def _radar_tick(corridor: Corridor, run_prefix: str, as_of: date, store: State) -> str:
    tier1 = run_tier1(corridor, RADAR_PRODUCT, store=store, as_of=as_of)
    if tier1.signal is None or not tier1.signal.outside_band:
        return "quiet"
    classification = run_tier2(tier1.signal, f"{run_prefix}_{as_of.isoformat()}")
    if classification != "investigate":
        return "quiet"
    handoff(corridor, "lhende_barrier", tier1.signal, store=store)
    return "handoff"


def run_replay(
    corridor: Corridor,
    run_prefix: str,
    store: State | None = None,
    tick_real_seconds: float = 1.0,
    deterministic: bool = False,
) -> ReplaySummary:
    target = store or default_state
    clock = build_clock(corridor)
    ticks: list[ReplayTick] = []
    tool_sequences: list[tuple[str, ...]] = []
    previous_as_of: date | None = None

    while True:
        as_of = clock.as_of()
        outcome = "quiet"
        run_id: str | None = None
        for feature_id in _features_newly_due(corridor, as_of, previous_as_of):
            run_id, tools = _investigate_feature(
                corridor, feature_id, run_prefix, as_of, target, deterministic
            )
            tool_sequences.append(tools)
            outcome = "investigated"
        if outcome == "quiet":
            outcome = _radar_tick(corridor, run_prefix, as_of, target)
        ticks.append(ReplayTick(clock.simulated_now(), as_of, outcome, run_id))
        previous_as_of = as_of
        if clock.finished():
            break
        time.sleep(tick_real_seconds)

    return ReplaySummary(tuple(ticks), tuple(tool_sequences))
