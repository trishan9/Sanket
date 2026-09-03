from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from core.config import settings
from core.errors import BaselineNotEstimableError
from core.state import State
from core.state import state as default_state

MIN_OBSERVATIONS_FOR_VARIANCE = 3


@dataclass(frozen=True)
class Baseline:
    product: str
    tile: str
    statistic: str
    value: float
    variance: float
    n_obs: int
    computed_at: datetime
    warming_up: bool

    def z_score(self, observed: float) -> float:
        if self.variance <= 0:
            return 0.0 if observed == self.value else float("inf")
        return (observed - self.value) / float(np.sqrt(self.variance))


def rolling_statistics(values: list[float]) -> tuple[float, float, int]:
    window = values[-settings.baseline_observations :]
    array = np.array(window)
    mean = float(array.mean())
    variance = float(array.var(ddof=1)) if len(array) >= MIN_OBSERVATIONS_FOR_VARIANCE else 0.0
    return mean, variance, len(array)


def compute_baseline(
    product: str,
    tile: str,
    statistic: str,
    historical_values: list[float],
) -> Baseline:
    if not historical_values:
        raise BaselineNotEstimableError(f"no observations for {product}/{tile}/{statistic}")
    mean, variance, n_obs = rolling_statistics(historical_values)
    warming_up = n_obs < settings.baseline_observations
    return Baseline(
        product=product,
        tile=tile,
        statistic=statistic,
        value=mean,
        variance=variance,
        n_obs=n_obs,
        computed_at=datetime.now(UTC),
        warming_up=warming_up,
    )


def store_baseline(baseline: Baseline, store: State | None = None) -> None:
    target = store or default_state
    with target.connect() as connection:
        connection.execute(
            "INSERT INTO baselines (product, tile, statistic, value, variance, n_obs, "
            "computed_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(product, tile, statistic) DO UPDATE SET value=excluded.value, "
            "variance=excluded.variance, n_obs=excluded.n_obs, computed_at=excluded.computed_at",
            (
                baseline.product,
                baseline.tile,
                baseline.statistic,
                baseline.value,
                baseline.variance,
                baseline.n_obs,
                baseline.computed_at.isoformat(),
            ),
        )


def load_baseline(
    product: str, tile: str, statistic: str, store: State | None = None
) -> Baseline | None:
    target = store or default_state
    with target.connect() as connection:
        row = connection.execute(
            "SELECT * FROM baselines WHERE product=? AND tile=? AND statistic=?",
            (product, tile, statistic),
        ).fetchone()
    if row is None:
        return None
    return Baseline(
        product=row["product"],
        tile=row["tile"],
        statistic=row["statistic"],
        value=row["value"],
        variance=row["variance"],
        n_obs=row["n_obs"],
        computed_at=datetime.fromisoformat(row["computed_at"]),
        warming_up=row["n_obs"] < settings.baseline_observations,
    )
