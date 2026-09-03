from __future__ import annotations

from actions.actor import act
from agent.decision import Confidence
from agent.explainer import ExplainerOutput, explain
from agent.ledger import Ledger
from agent.trace import Trace
from agent.verifier import verify
from core.corridor import Corridor
from core.state import State


def confidence_of(ledger: Ledger) -> Confidence:
    for claim in reversed(ledger.claims):
        if not claim.vetoed:
            return claim.confidence
    return "insufficient"


def run_verifier_explainer_actor(
    corridor: Corridor,
    ledger: Ledger,
    run_id: str,
    trace: Trace,
    store: State,
    *,
    replay: bool = False,
) -> ExplainerOutput:
    table = verify(ledger, run_id, trace)
    confidence = confidence_of(ledger)
    settlement_lead_times: dict[str, float | None] = dict.fromkeys(corridor.settlement_names)
    output = explain(ledger, table, confidence, corridor.settlement_names, run_id)
    trace.explain(f"decision {output.decision.status}, score {output.decision.score:.2f}")
    settlement = corridor.settlement_names[0] if corridor.settlement_names else corridor.basin_id
    result = act(
        output,
        settlement,
        corridor.basin_id,
        run_id,
        settlement_lead_times,
        replay=replay,
        store=store,
        corridor=corridor,
    )
    trace.action(f"actor: {result}")
    return output
