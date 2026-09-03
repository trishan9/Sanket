from __future__ import annotations

from dataclasses import dataclass

from analysis.risk.cascade_graph import NODE_TO_DAM, build_graph
from analysis.risk.prediction import INDICATOR_BY_KEY, estimate_hazard
from analysis.risk.schemas import HazardNode
from core.corridor import Corridor

TIE_MARGIN = 0.12
FORMED_TYPES = frozenset({"barrier_lake", "landslide_dam", "debris_dam"})

ATTRIBUTION_CAVEATS: tuple[str, ...] = (
    "this ranks which upstream sources are consistent with the observation, it does not "
    "establish that any of them caused it",
    "two candidates within a narrow margin are reported as indistinguishable rather than "
    "resolved by tie-break",
    "a candidate that could not be observed is carried at its prior and flagged, never dropped",
    "establishing the cause of a specific event requires a dedicated field and imagery study",
)


@dataclass(frozen=True)
class CandidateCause:
    node_id: str
    node_type: str
    steps_downstream: int
    prior_probability: float
    posterior_probability: float
    supporting: tuple[str, ...]
    contradicting: tuple[str, ...]
    unobserved: tuple[str, ...]
    share: float

    def rendered(self) -> str:
        return (
            f"{self.node_id} ({self.node_type.replace('_', ' ')}), {self.steps_downstream} step(s) "
            f"upstream: {self.share * 100:.0f}% of the evidence weight, hazard estimate "
            f"{self.posterior_probability * 100:.1f}% against a "
            f"{self.prior_probability * 100:.1f}% prior"
        )


@dataclass(frozen=True)
class Attribution:
    observed_at: str
    window_days: int
    candidates: tuple[CandidateCause, ...]
    indistinguishable: tuple[str, ...]
    caveats: tuple[str, ...] = ATTRIBUTION_CAVEATS

    @property
    def leading(self) -> CandidateCause | None:
        return self.candidates[0] if self.candidates else None

    def rendered(self) -> str:
        if not self.candidates:
            return (
                "no upstream source node is consistent with an observation at "
                f"{self.observed_at}"
            )
        if self.indistinguishable:
            joined = " and ".join(self.indistinguishable)
            return (
                f"observation at {self.observed_at}: {joined} are within the tie margin and "
                "cannot be separated on this evidence"
            )
        best = self.candidates[0]
        return (
            f"observation at {self.observed_at}: {best.node_id} carries the most evidence weight "
            f"at {best.share * 100:.0f}%, but this is consistency, not established causation"
        )


def _upstream_of(
    nodes: dict[str, HazardNode], observed_at: str
) -> list[tuple[HazardNode, int]]:
    chain: list[tuple[HazardNode, int]] = []
    for node in nodes.values():
        if node.node_type == "settlement":
            continue
        steps = _steps_between(nodes, node.node_id, observed_at)
        if steps is not None:
            chain.append((node, steps))
    return sorted(chain, key=lambda item: item[1])


def _steps_between(nodes: dict[str, HazardNode], origin: str, target: str) -> int | None:
    seen: set[str] = set()
    frontier = [(origin, 0)]
    while frontier:
        current, depth = frontier.pop(0)
        if current == target:
            return depth
        if current in seen:
            continue
        seen.add(current)
        node = nodes.get(current)
        if node is None:
            continue
        frontier.extend((child, depth + 1) for child in node.downstream)
    return None


EvidenceSplit = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]


def _evidence_split(observations: dict[str, bool | None]) -> EvidenceSplit:
    supporting: list[str] = []
    contradicting: list[str] = []
    unobserved: list[str] = []
    for key, indicator in INDICATOR_BY_KEY.items():
        state = observations.get(key)
        if state is None:
            unobserved.append(indicator.label)
        elif state:
            supporting.append(f"{indicator.label} (LR {indicator.likelihood_ratio_present:g})")
        else:
            contradicting.append(
                f"{indicator.label} absent (LR {indicator.likelihood_ratio_absent:g})"
            )
    return tuple(supporting), tuple(contradicting), tuple(unobserved)


def _score_candidate(
    node: HazardNode,
    steps: int,
    observations_by_node: dict[str, dict[str, bool | None]],
    window_days: int,
    days_since_formation: float,
) -> CandidateCause:
    observations = observations_by_node.get(node.node_id, {})
    estimate = estimate_hazard(
        node.node_id,
        NODE_TO_DAM.get(node.node_type, "unknown"),
        observations,
        window_days,
        already_formed=node.node_type in FORMED_TYPES,
        days_since_formation=days_since_formation,
    )
    supporting, contradicting, unobserved = _evidence_split(observations)
    return CandidateCause(
        node_id=node.node_id,
        node_type=node.node_type,
        steps_downstream=steps,
        prior_probability=estimate.prior_probability,
        posterior_probability=estimate.posterior_probability,
        supporting=supporting,
        contradicting=contradicting,
        unobserved=unobserved,
        share=0.0,
    )


def attribute(
    corridor: Corridor,
    observed_at: str,
    observations_by_node: dict[str, dict[str, bool | None]],
    window_days: int = 7,
    days_since_formation: float = 1.0,
) -> Attribution:
    nodes = build_graph(corridor)
    candidates = [
        _score_candidate(node, steps, observations_by_node, window_days, days_since_formation)
        for node, steps in _upstream_of(nodes, observed_at)
    ]
    total = sum(item.posterior_probability for item in candidates)
    scored = [
        CandidateCause(
            **{**vars(item), "share": item.posterior_probability / total if total else 0.0}
        )
        for item in candidates
    ]
    scored.sort(key=lambda item: item.share, reverse=True)
    tied: tuple[str, ...] = ()
    if len(scored) >= 2 and abs(scored[0].share - scored[1].share) < TIE_MARGIN:
        tied = (scored[0].node_id, scored[1].node_id)
    return Attribution(
        observed_at=observed_at,
        window_days=window_days,
        candidates=tuple(scored),
        indistinguishable=tied,
    )
