from __future__ import annotations

from typing import Any

from actions.whatsapp import send_gate_request
from agent.explainer import ExplainerOutput
from core.board import requires_approval
from core.board import write_status as board_write_status
from core.corridor import Corridor
from core.state import State


def _why_panel_payload(output: ExplainerOutput) -> dict[str, Any]:
    pack = output.evidence_pack
    return {
        "decision_score": pack.score,
        "contributions": list(pack.contributions),
        "counterfactuals": [
            {
                "change": c.change,
                "new_status": c.new_status,
                "new_lead_time_minutes": c.new_lead_time_minutes,
            }
            for c in pack.counterfactuals
        ],
        "flip_points": list(pack.flip_point_summary),
        "what_would_change_my_mind": list(pack.what_would_change_my_mind),
        "public_note_english": output.public_note.english,
        "public_note_nepali": output.public_note.nepali,
        "vetoed": output.vetoed,
    }


def act(
    output: ExplainerOutput,
    settlement: str,
    basin_id: str,
    run_id: str,
    settlement_lead_times: dict[str, float | None],
    *,
    replay: bool = False,
    store: State | None = None,
    corridor: Corridor | None = None,
) -> dict[str, Any]:
    status = output.decision.status
    if not requires_approval(status):
        result = board_write_status(
            settlement,
            basin_id,
            status,
            lead_time_minutes=settlement_lead_times.get(settlement),
            confidence=_confidence_label(output),
            run_id=run_id,
            store=store,
            extra=_why_panel_payload(output),
        )
        return {"autonomous": True, "board_write": result}
    record, outcome = send_gate_request(
        output, run_id, settlement_lead_times, replay=replay, store=store, corridor=corridor
    )
    return {
        "autonomous": False,
        "gate_id": record.gate_id,
        "gate_deadline": record.deadline.isoformat(),
        "gate_request_status": outcome.result.status,
    }


def _confidence_label(output: ExplainerOutput) -> str | None:
    for contribution in output.decision.contributions:
        if contribution.term == "confidence":
            return contribution.raw_value
    return None
