from __future__ import annotations

import re

import pytest

from analysis.risk.base_rates import base_rate_by_dam_type, poisson_rate_interval
from analysis.risk.cascade_sim import simulate_cascade
from analysis.risk.observability import DETECTION_LIMIT_KM2, observability_report
from analysis.risk.susceptibility import rank_pdgls, susceptibility_at
from core.corridor import load_all_corridors

FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"probability of failure",
    r"chance of failure",
    r"likelihood of failure",
    r"will fail",
    r"will burst",
    r"will breach",
    r"expected to fail",
    r"\d+\s*%\s*(chance|probability|risk of failure)",
)

NEGATORS: tuple[str, ...] = ("not", "never", "no ", "rather than", "without")

DATE_PREDICTION = re.compile(
    r"(will|going to|expected to|forecast to)\s+(fail|breach|burst)[^.]{0,40}\b(19|20)\d{2}\b",
    re.I,
)


def _is_negated(lowered: str, start: int) -> bool:
    window = lowered[max(0, start - 60) : start]
    return any(negator in window for negator in NEGATORS)


@pytest.fixture
def corridor():  # type: ignore[no-untyped-def]
    return load_all_corridors()["bhotekoshi"]


def _all_rendered_strings(corridor) -> list[str]:  # type: ignore[no-untyped-def]
    strings: list[str] = []
    for score in rank_pdgls():
        strings.append(score.rendered())
        strings.extend(score.caveats)
        strings.extend(rate.rendered() for rate in score.base_rates)
        strings.extend(rate.caveat for rate in score.base_rates)
    cascade = simulate_cascade(corridor, "lhende_barrier", 1.0)
    strings.append(cascade.rendered())
    strings.extend(cascade.caveats)
    strings.extend(step.mechanism for step in cascade.steps)
    report = observability_report("Koshi")
    strings.append(report.rendered())
    strings.extend(report.caveats)
    return strings


def test_no_output_states_a_probability_or_date_of_failure(corridor) -> None:
    offenders: list[str] = []
    for text in _all_rendered_strings(corridor):
        lowered = text.lower()
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, lowered):
                if not _is_negated(lowered, match.start()):
                    offenders.append(f"{pattern!r} asserted in {text!r}")
        if DATE_PREDICTION.search(text):
            offenders.append(f"date-of-failure prediction in {text!r}")
    assert not offenders, "risk output implied a failure probability or date:\n" + "\n".join(
        offenders
    )


def test_all_forty_seven_pdgls_are_scored_and_ranked() -> None:
    scores = rank_pdgls()
    assert len(scores) == 47
    ordered = [score.rank_score for score in scores]
    assert ordered == sorted(ordered, reverse=True)


def test_every_base_rate_carries_a_confidence_interval_and_sample_size() -> None:
    rates = base_rate_by_dam_type()
    assert rates
    for rate in rates.values():
        assert rate.sample_size > 0
        assert rate.ci_low <= rate.rate_per_lake <= rate.ci_high
        assert str(rate.sample_size) in rate.rendered()
        assert "CI" in rate.rendered()


def test_recurrent_ice_dammed_rate_may_exceed_one_and_says_why() -> None:
    ice = base_rate_by_dam_type()["ice"]
    assert ice.rate_per_lake > 1.0
    assert ice.ci_high > 1.0
    assert "recurrent" in ice.caveat


def test_poisson_interval_brackets_the_point_estimate() -> None:
    low, high = poisson_rate_interval(390, 2002)
    assert low < 390 / 2002 < high


def test_cascade_confidence_decays_with_chain_length(corridor) -> None:
    result = simulate_cascade(corridor, "lhende_barrier", 1.0)
    assert len(result.steps) >= 3
    confidences = [step.confidence for step in result.steps]
    assert confidences == sorted(confidences, reverse=True)
    assert result.terminal_confidence < confidences[0]
    assert "decays" in result.rendered()


def test_below_detection_limit_reports_not_observable_never_not_present() -> None:
    report = observability_report("Koshi")
    assert report.detection_limit_km2 == DETECTION_LIMIT_KM2
    assert "not observable" in report.rendered()
    assert "not present" in report.rendered()
    joined = " ".join(report.caveats).lower()
    assert "never not present" in joined


def test_susceptibility_reports_parameters_it_could_not_observe() -> None:
    score = susceptibility_at(rank_pdgls()[0].node_id)
    assert score is not None
    assert score.unobservable_parameters
    assert "freeboard" in score.unobservable_parameters
