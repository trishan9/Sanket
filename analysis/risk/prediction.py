from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from analysis.risk.base_rates import base_rate_by_dam_type
from analysis.risk.schemas import DamType

RECORD_YEARS = 190.0
COMPLETENESS_RANGE = (0.30, 0.80)
MONTE_CARLO_DRAWS = 20000
RANDOM_SEED = 20260904

METHOD_NAME = "Bayesian indicator update on an empirical base rate"

FORMED_DAM_EVENTUAL_FAILURE = 0.85
FORMED_DAM_MEDIAN_DAYS = 10.0
FORMED_DAM_CITATION = (
    "Costa and Schuster 1988, GSA Bulletin 100:1054, survey of natural dams: about 85 percent "
    "eventually fail and about half of those fail within 10 days of formation"
)

FORMED_DAM_STEPS: tuple[str, ...] = (
    "1. Prior. A dam that has already formed is not asking whether one will appear, so the "
    "inventory rate does not apply. Costa and Schuster 1988 surveyed natural dams and found "
    "about 85 percent eventually fail, roughly half of those within 10 days of formation.",
    "2. Survival. Model that as a defective exponential: an 0.85 ceiling on eventual failure "
    "with failure timing among the ones that do fail following a 10-day median. The remaining "
    "15 percent are treated as stabilising permanently.",
    "3. Conditioning. Condition on the dam having already survived the days since it formed, so "
    "a dam that has held for weeks carries a lower forward probability than a fresh one.",
    "4. Evidence. Multiply the prior odds by a likelihood ratio for every observed indicator; an "
    "indicator that could not be observed contributes exactly 1.0.",
    "5. Interval. Monte Carlo over the eventual-failure ceiling and the median timing, reporting "
    "the median with a 90 percent credible interval.",
)

METHOD_STEPS: tuple[str, ...] = (
    "1. Prior. Take the dam-type base rate measured from HMAGLOFDB events joined against the "
    "ICIMOD 2015 inventory, and convert it to a per-lake-year Poisson rate by dividing by the "
    "190-year record span.",
    "2. Under-reporting. The documentary record is incomplete, so the observed rate is a lower "
    "bound. Divide by a completeness factor drawn uniformly from 0.30-0.80, which raises the "
    "true rate and widens the interval rather than pretending the record is complete.",
    "3. Window. Convert the rate to a prior probability of at least one event in the requested "
    "window with 1 - exp(-lambda * years).",
    "4. Evidence. Multiply the prior odds by a likelihood ratio for every indicator that was "
    "actually observed. An indicator that could not be observed contributes a ratio of exactly "
    "1.0 and moves nothing.",
    "5. Interval. Repeat the whole chain over Monte Carlo draws of the Poisson rate and the "
    "completeness factor, and report the median with a 90 percent credible interval.",
)

MODEL_CAVEATS: tuple[str, ...] = (
    "this is a probability of at least one outburst-type event in a stated window for a lake of "
    "this class carrying these indicators, not a statement about a specific date",
    "likelihood ratios are elicited from the cited literature, not fitted on a labelled "
    "training set, because no such set exists at this sample size",
    "indicators that could not be observed contribute nothing and are listed by name",
    "the base rate is drawn from a documentary record that is demonstrably incomplete, which is "
    "why the completeness factor widens rather than narrows the interval",
    "a probability is not a forecast of occurrence; the consequence model downstream of this is "
    "the part validated against observed flood extent",
)


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    likelihood_ratio_present: float
    likelihood_ratio_absent: float
    citation: str
    rationale: str


INDICATORS: tuple[Indicator, ...] = (
    Indicator(
        key="seismic_landslide_type",
        label="Landslide-type seismic event in basin",
        likelihood_ratio_present=42.0,
        likelihood_ratio_absent=0.85,
        citation="USGS ANSS event-type classification; Costa and Schuster 1988 GSA Bull 100:1054",
        rationale=(
            "A mass movement large enough to register seismically is the dominant impoundment "
            "mechanism on this river system and is near-instantaneous, so its presence moves the "
            "estimate far more than any slow indicator."
        ),
    ),
    Indicator(
        key="upstream_mass_movement",
        label="Confirmed disturbance upstream of the lake",
        likelihood_ratio_present=8.5,
        likelihood_ratio_absent=0.80,
        citation="OPERA DIST-ALERT-HLS; Gruber and Haeberli 2007 JGR 112:F02S18",
        rationale=(
            "Fresh surface disturbance above a lake indicates material delivery into it, the "
            "displacement-wave pathway. Cloud limits detection, so absence is weak evidence."
        ),
    ),
    Indicator(
        key="radar_water_anomaly",
        label="Radar water-extent anomaly against rolling baseline",
        likelihood_ratio_present=6.0,
        likelihood_ratio_absent=0.55,
        citation="OPERA DSWx-S1 against this system's own 14-observation rolling baseline",
        rationale=(
            "A step change in water extent that survives the z-test is direct evidence of "
            "impoundment or drainage. Radar sees through cloud, so absence is meaningful here."
        ),
    ),
    Indicator(
        key="lake_area_growth",
        label="Sustained lake-area growth",
        likelihood_ratio_present=3.2,
        likelihood_ratio_absent=0.70,
        citation="Shugar et al. 2020 Nature Climate Change 10:939; Rounce et al. 2016 HESS 20:3455",
        rationale=(
            "Growing lakes are over-represented among failures because volume and dam loading "
            "both rise. This is a conditioning trend, not a trigger, so the ratio is modest."
        ),
    ),
    Indicator(
        key="antecedent_precip_extreme",
        label="Extreme antecedent rainfall",
        likelihood_ratio_present=2.1,
        likelihood_ratio_absent=0.95,
        citation="CHIRPS v2.0 percentile against 21-year same-month climatology",
        rationale=(
            "Rainfall can load a moraine dam, but both events on this corridor occurred on "
            "unremarkable rainfall days, so its absence barely lowers the estimate."
        ),
    ),
    Indicator(
        key="temperature_anomaly",
        label="Positive temperature anomaly",
        likelihood_ratio_present=1.6,
        likelihood_ratio_absent=1.0,
        citation="Peer-reviewed Thame 2024 reconstruction",
        rationale=(
            "A conditioning factor associated with a tipping point, not causal on its own. Its "
            "absence is treated as uninformative."
        ),
    ),
)

INDICATOR_BY_KEY: dict[str, Indicator] = {item.key: item for item in INDICATORS}


@dataclass(frozen=True)
class IndicatorReading:
    key: str
    state: str
    detail: str = ""
    likelihood_ratio: float = 1.0
    log_contribution: float = 0.0


@dataclass(frozen=True)
class HazardEstimate:
    node_id: str
    dam_type: DamType
    window_days: int
    prior_probability: float
    posterior_probability: float
    credible_interval: tuple[float, float]
    readings: tuple[IndicatorReading, ...]
    unobserved: tuple[str, ...]
    dominant_indicator: str | None
    method: str = METHOD_NAME
    steps: tuple[str, ...] = field(default=METHOD_STEPS)
    caveats: tuple[str, ...] = field(default=MODEL_CAVEATS)

    @property
    def lift(self) -> float:
        if self.prior_probability <= 0:
            return 0.0
        return self.posterior_probability / self.prior_probability

    def rendered(self) -> str:
        low, high = self.credible_interval
        return (
            f"{self.node_id}: {self.posterior_probability * 100:.2f}% chance of at least one "
            f"outburst-type event in {self.window_days} days "
            f"(90% credible interval {low * 100:.2f}-{high * 100:.2f}%), against a "
            f"{self.prior_probability * 100:.3f}% base rate for a {self.dam_type}-dammed lake. "
            "This is a probability for a lake of this class carrying these indicators, not a "
            "statement about a specific date."
        )


def _odds(probability: float) -> float:
    bounded = min(max(probability, 1e-12), 1 - 1e-12)
    return bounded / (1 - bounded)


def _probability(odds: float) -> float:
    return odds / (1 + odds)


def prior_rate_per_lake_year(dam_type: DamType) -> tuple[float, float, float]:
    rate = base_rate_by_dam_type().get(dam_type)
    if rate is None:
        return (0.0, 0.0, 0.0)
    scale = 1.0 / RECORD_YEARS
    return (rate.rate_per_lake * scale, rate.ci_low * scale, rate.ci_high * scale)


def _readings_from(observations: dict[str, bool | None]) -> list[IndicatorReading]:
    readings: list[IndicatorReading] = []
    for indicator in INDICATORS:
        observed = observations.get(indicator.key)
        if observed is None:
            readings.append(
                IndicatorReading(indicator.key, "not observed", "contributes nothing", 1.0, 0.0)
            )
            continue
        ratio = (
            indicator.likelihood_ratio_present
            if observed
            else indicator.likelihood_ratio_absent
        )
        readings.append(
            IndicatorReading(
                key=indicator.key,
                state="present" if observed else "absent",
                detail=indicator.rationale,
                likelihood_ratio=ratio,
                log_contribution=math.log(ratio),
            )
        )
    return readings


def formed_dam_prior_draws(
    window_days: int, days_since_formation: float, rng: np.random.Generator
) -> np.ndarray:
    ceiling = rng.uniform(0.75, 0.92, MONTE_CARLO_DRAWS)
    median_days = rng.uniform(5.0, 20.0, MONTE_CARLO_DRAWS)
    decay = np.log(2.0) / median_days
    survived = np.exp(-decay * days_since_formation)
    still_standing = 1.0 - ceiling * (1.0 - survived)
    fails_by_end = ceiling * (1.0 - np.exp(-decay * (days_since_formation + window_days)))
    fails_already = ceiling * (1.0 - survived)
    forward: np.ndarray = np.clip(
        (fails_by_end - fails_already) / np.maximum(still_standing, 1e-9), 0.0, 1.0
    )
    return forward


def _prior_draws(
    dam_type: DamType,
    window_days: int,
    already_formed: bool,
    days_since_formation: float,
) -> tuple[np.ndarray, tuple[str, ...]]:
    median_rate, low_rate, high_rate = prior_rate_per_lake_year(dam_type)
    rng = np.random.default_rng(RANDOM_SEED)
    if already_formed or median_rate <= 0.0:
        return formed_dam_prior_draws(window_days, days_since_formation, rng), FORMED_DAM_STEPS
    years = window_days / 365.25
    rates = rng.uniform(low_rate, max(high_rate, low_rate + 1e-12), MONTE_CARLO_DRAWS)
    completeness = rng.uniform(*COMPLETENESS_RANGE, MONTE_CARLO_DRAWS)
    draws: np.ndarray = 1.0 - np.exp(-(rates / completeness) * years)
    return draws, METHOD_STEPS


def estimate_hazard(
    node_id: str,
    dam_type: DamType,
    observations: dict[str, bool | None],
    window_days: int = 30,
    *,
    already_formed: bool = False,
    days_since_formation: float = 0.0,
) -> HazardEstimate:
    readings = _readings_from(observations)
    log_lr = sum(reading.log_contribution for reading in readings)
    prior_draws, steps = _prior_draws(
        dam_type, window_days, already_formed, days_since_formation
    )
    prior_point = float(np.median(prior_draws))
    posterior_draws = np.array(
        [_probability(_odds(float(p)) * math.exp(log_lr)) for p in prior_draws]
    )
    observed_readings = [r for r in readings if r.state != "not observed"]
    dominant = (
        max(observed_readings, key=lambda r: abs(r.log_contribution)).key
        if observed_readings
        else None
    )
    return HazardEstimate(
        node_id=node_id,
        dam_type=dam_type,
        window_days=window_days,
        prior_probability=prior_point,
        posterior_probability=float(np.median(posterior_draws)),
        credible_interval=(
            float(np.percentile(posterior_draws, 5)),
            float(np.percentile(posterior_draws, 95)),
        ),
        readings=tuple(readings),
        unobserved=tuple(r.key for r in readings if r.state == "not observed"),
        dominant_indicator=dominant,
        steps=steps,
    )
