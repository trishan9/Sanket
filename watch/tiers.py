from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from agent.router import Lane, gateway
from agent.trace import Trace
from analysis.eo import radar
from analysis.eo.baselines import compute_baseline, load_baseline, store_baseline
from analysis.eo.changedetect import ChangeSignal, classify
from analysis.eo.dswx import WaterObservation, observations_for_tile, water_area_km2
from core.corridor import Corridor
from core.errors import AllProvidersFailedError
from core.state import State, now_iso
from core.state import state as default_state

RADAR_PRODUCT = "sentinel-1-rtc-radar"
RADAR_AOI_KEY = "bhotekoshi_aoi"
LHENDE_BARRIER_WINDOW_M: tuple[float, float, float, float] = (
    338311.73,
    3125791.10,
    343311.73,
    3130791.10,
)

Classification = Literal["investigate", "artefact", "seasonal", "insufficient_data"]
CLASSIFY_LANE: Lane = "sanket-classify"
RECHECK_HOURS_OPEN_ANOMALY = 6

CLASSIFY_SYSTEM_PROMPT = (
    "You classify a water-area anomaly at a glacial-hazard corridor. Given the z-score "
    "and season, answer with exactly one word: investigate, artefact, seasonal, or "
    "insufficient_data. Radar layover/shadow and wet-snow backscatter produce artefacts. "
    "Snowmelt produces seasonal increases. Reply with the single word only."
)


@dataclass(frozen=True)
class Tier1Result:
    tile: str
    signal: ChangeSignal | None
    baseline_updated: bool


CORRIDOR_TILES: dict[str, str] = {"bhotekoshi_trishuli": "T45RUL"}


def _tile_for(corridor: Corridor) -> str | None:
    return CORRIDOR_TILES.get(corridor.basin_id)


def _tier1_from_observations[T](
    product: str,
    tile: str,
    observations: list[T],
    value_of: Callable[[T], float],
    store: State,
) -> Tier1Result:
    if not observations:
        return Tier1Result(tile, None, False)
    observed = value_of(observations[-1])
    baseline = load_baseline(product, tile, "water_area_km2", store)
    if baseline is None:
        history = [value_of(o) for o in observations]
        baseline = compute_baseline(product, tile, "water_area_km2", history)
        store_baseline(baseline, store)
        return Tier1Result(tile, None, True)

    signal = classify(observed, baseline)
    updated = False
    if signal.classification == "within_band":
        history = [value_of(o) for o in observations]
        refreshed = compute_baseline(product, tile, "water_area_km2", history)
        store_baseline(refreshed, store)
        updated = True
    return Tier1Result(tile, signal, updated)


def _dswx_observations(tile: str, as_of: date | None) -> list[WaterObservation]:
    observations = observations_for_tile(tile)
    if as_of is None:
        return list(observations)
    return [o for o in observations if o.acquired.date() <= as_of]


def _radar_observations(as_of: date | None) -> list[radar.RadarWaterObservation]:
    observations = sorted(
        (
            radar.detect_water(p, window_bounds_m=LHENDE_BARRIER_WINDOW_M)
            for p in radar.list_vv_files()
        ),
        key=lambda o: o.acquired,
    )
    if as_of is None:
        return observations
    return [o for o in observations if o.acquired.date() <= as_of]


def run_tier1(
    corridor: Corridor, product: str, store: State | None = None, as_of: date | None = None
) -> Tier1Result:
    target = store or default_state
    if product == RADAR_PRODUCT:
        radar_observations = _radar_observations(as_of)
        return _tier1_from_observations(
            RADAR_PRODUCT, RADAR_AOI_KEY, radar_observations, radar.water_area_km2, target
        )
    tile = _tile_for(corridor)
    if tile is None:
        return Tier1Result(corridor.basin_id, None, False)
    dswx_observations = _dswx_observations(tile, as_of)
    return _tier1_from_observations(product, tile, dswx_observations, water_area_km2, target)


def run_tier2(signal: ChangeSignal, run_id: str, trace: Trace | None = None) -> Classification:
    messages = [
        {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"z-score {signal.z:.2f}, classification band {signal.classification}, "
                f"observed value {signal.observed:.4f}, baseline mean "
                f"{signal.baseline.value:.4f} variance {signal.baseline.variance:.4f}."
            ),
        },
    ]
    try:
        response = gateway.complete(
            CLASSIFY_LANE, messages, run_id=run_id, trace=trace, max_tokens=10
        )
    except AllProvidersFailedError:
        if trace is not None:
            trace.degraded(
                "tier2 classify: no provider reachable - deterministic mode defaults to the "
                "conservative outcome 'investigate' rather than silently dropping the anomaly"
            )
        return "investigate"
    word = (response["content"] or "").strip().lower()
    return _coerce_classification(word)


def _coerce_classification(word: str) -> Classification:
    valid: dict[str, Classification] = {
        "investigate": "investigate",
        "artefact": "artefact",
        "seasonal": "seasonal",
        "insufficient_data": "insufficient_data",
    }
    return valid.get(word, "insufficient_data")


def fingerprint(location_cell: str, feature_id: str, change_signature: str) -> str:
    payload = f"{location_cell}|{feature_id}|{change_signature}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _find_anomaly(fingerprint_value: str, store: State) -> dict[str, object] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM anomalies WHERE fingerprint=?", (fingerprint_value,)
        ).fetchone()
    return dict(row) if row else None


def _open_anomaly(
    anomaly_id: str,
    corridor: Corridor,
    fingerprint_value: str,
    location: str,
    observed: float,
    store: State,
) -> None:
    with store._lock, store.connect() as connection:
        connection.execute(
            "INSERT INTO anomalies (anomaly_id, basin_id, fingerprint, location, "
            "first_seen, status, growth_history) VALUES (?,?,?,?,?,'open',?)",
            (
                anomaly_id,
                corridor.basin_id,
                fingerprint_value,
                location,
                now_iso(),
                json.dumps([observed]),
            ),
        )


def _update_anomaly(anomaly_id: str, observed: float, store: State) -> None:
    with store._lock, store.connect() as connection:
        row = connection.execute(
            "SELECT growth_history FROM anomalies WHERE anomaly_id=?", (anomaly_id,)
        ).fetchone()
        history = json.loads(row["growth_history"]) if row else []
        history.append(observed)
        connection.execute(
            "UPDATE anomalies SET growth_history=?, last_investigated=?, "
            "next_recheck=? WHERE anomaly_id=?",
            (
                json.dumps(history),
                now_iso(),
                (datetime.now(UTC) + timedelta(hours=RECHECK_HOURS_OPEN_ANOMALY)).isoformat(),
                anomaly_id,
            ),
        )


def handoff(
    corridor: Corridor,
    feature_id: str,
    signal: ChangeSignal,
    store: State | None = None,
) -> tuple[str, bool]:
    from watch.queue import enqueue

    target = store or default_state
    z_bucket = (
        "inf"
        if not isinstance(signal.z, float) or signal.z in (float("inf"), float("-inf"))
        else str(round(signal.z))
    )
    change_signature = f"{signal.classification}:{z_bucket}"
    fp = fingerprint(corridor.basin_id, feature_id, change_signature)
    existing = _find_anomaly(fp, target)

    if existing is not None:
        _update_anomaly(str(existing["anomaly_id"]), signal.observed, target)
        anomaly_id = str(existing["anomaly_id"])
        is_new = False
    else:
        anomaly_id = f"anom_{fp[:8]}"
        _open_anomaly(anomaly_id, corridor, fp, feature_id, signal.observed, target)
        is_new = True

    job_id = enqueue(
        corridor.basin_id,
        "investigate",
        {
            "anomaly_id": anomaly_id,
            "feature_id": feature_id,
            "z": signal.z,
            "observed": signal.observed,
            "is_new": is_new,
        },
        store=target,
    )
    return job_id, is_new
