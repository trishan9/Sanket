from __future__ import annotations

from analysis.risk.schemas import DamType, HazardNode, NodeType
from core.corridor import Corridor

FEATURE_TYPE_TO_NODE: dict[str, NodeType] = {
    "supraglacial_lake": "supraglacial_lake",
    "barrier_lake": "barrier_lake",
    "moraine_lake": "moraine_lake",
    "ice_dammed_lake": "ice_dammed_lake",
    "landslide_dam": "landslide_dam",
    "debris_dam": "debris_dam",
    "reservoir": "reservoir",
}

NODE_TO_DAM: dict[NodeType, DamType] = {
    "moraine_lake": "moraine",
    "ice_dammed_lake": "ice",
    "supraglacial_lake": "ice",
    "bedrock_lake": "bedrock",
    "landslide_dam": "landslide_debris",
    "debris_dam": "landslide_debris",
    "barrier_lake": "landslide_debris",
    "reservoir": "unknown",
    "confluence": "unknown",
    "settlement": "unknown",
}

NON_GLACIAL_NODE_TYPES: tuple[NodeType, ...] = (
    "landslide_dam",
    "debris_dam",
    "barrier_lake",
    "reservoir",
    "confluence",
)


def build_graph(corridor: Corridor) -> dict[str, HazardNode]:
    nodes: dict[str, HazardNode] = {}
    ordered_settlements = list(corridor.downstream_reach)
    first_settlement = ordered_settlements[0].name if ordered_settlements else corridor.basin_id
    for feature in corridor.watched_features:
        node_type = FEATURE_TYPE_TO_NODE.get(feature.type, "barrier_lake")
        nodes[feature.id] = HazardNode(
            node_id=feature.id,
            node_type=node_type,
            location=feature.location,
            dam_type=NODE_TO_DAM.get(node_type, "unknown"),
            label=feature.id.replace("_", " "),
            downstream=(first_settlement,),
        )
    previous: str | None = None
    for station in ordered_settlements:
        nodes[station.name] = HazardNode(
            node_id=station.name,
            node_type="settlement",
            location=station.location,
            label=f"{station.name} ({station.district})",
            downstream=(),
        )
        if previous is not None:
            earlier = nodes[previous]
            nodes[previous] = earlier.model_copy(update={"downstream": (station.name,)})
        previous = station.name
    return nodes


def downstream_chain(nodes: dict[str, HazardNode], origin_id: str) -> list[HazardNode]:
    chain: list[HazardNode] = []
    seen: set[str] = set()
    current = nodes.get(origin_id)
    while current is not None and current.node_id not in seen:
        chain.append(current)
        seen.add(current.node_id)
        following = current.downstream[0] if current.downstream else None
        current = nodes.get(following) if following else None
    return chain
