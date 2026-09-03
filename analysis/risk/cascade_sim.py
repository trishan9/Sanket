from __future__ import annotations

from analysis.risk.cascade_graph import build_graph, downstream_chain
from analysis.risk.schemas import (
    CONFIDENCE_DECAY_PER_STEP,
    CascadeResult,
    CascadeStep,
    HazardNode,
)
from core.corridor import Corridor

CASCADE_CAVEATS: tuple[str, ...] = (
    "a scenario chain, not a statement that any step will occur",
    "confidence decays with every additional step because each link compounds the "
    "uncertainty of the one before it",
    "routing runs on a DEM that predates any recent event",
    "a water-only shallow-water treatment, not a two-phase debris flow",
)

MECHANISM_BY_TYPE: dict[str, str] = {
    "supraglacial_lake": "supraglacial lake drains into the channel below",
    "moraine_lake": "moraine dam breaches and releases impounded water",
    "ice_dammed_lake": "ice dam fails and releases impounded water",
    "bedrock_lake": "bedrock-confined lake overtops",
    "landslide_dam": "landslide dam impounds the channel and then fails",
    "debris_dam": "debris dam impounds the channel and then fails",
    "barrier_lake": "barrier lake impounded behind the blockage releases",
    "reservoir": "reservoir receives the surge and passes or attenuates it",
    "confluence": "surge meets the confluence and combines with the trunk flow",
    "settlement": "surge arrives at the settlement reach",
}


def _mechanism(node: HazardNode) -> str:
    return MECHANISM_BY_TYPE.get(node.node_type, "surge propagates downstream")


def simulate_cascade(
    corridor: Corridor,
    origin_node_id: str,
    breach_volume_mm3: float | None = None,
    *,
    decay: float = CONFIDENCE_DECAY_PER_STEP,
) -> CascadeResult:
    nodes = build_graph(corridor)
    chain = downstream_chain(nodes, origin_node_id)
    steps: list[CascadeStep] = []
    confidence = 1.0
    volume = breach_volume_mm3
    for order, node in enumerate(chain):
        if order > 0:
            confidence *= decay
        note = ""
        if node.node_type in {"reservoir", "confluence"}:
            note = "non-glacial node on the same drainage network"
        steps.append(
            CascadeStep(
                order=order,
                node_id=node.node_id,
                node_type=node.node_type,
                mechanism=_mechanism(node),
                confidence=round(confidence, 4),
                volume_mm3=volume,
                note=note,
            )
        )
    terminal = steps[-1].confidence if steps else 0.0
    return CascadeResult(
        origin_node_id=origin_node_id,
        steps=tuple(steps),
        terminal_confidence=terminal,
        decay_per_step=decay,
        caveats=CASCADE_CAVEATS,
    )
