from __future__ import annotations

from dataclasses import dataclass

from agent.explainer import STATUS_ACTION_NEPALI, STATUS_NEPALI, ExplainerOutput

REPLAY_PREFIX = "[REPLAY - TEST] "


@dataclass(frozen=True)
class WhatsAppMessage:
    tier: str
    body: str


def _prefix(body: str, replay: bool) -> str:
    return f"{REPLAY_PREFIX}{body}" if replay else body


def resident_message(
    output: ExplainerOutput,
    settlement: str,
    lead_time_minutes: float | None,
    *,
    replay: bool = False,
) -> WhatsAppMessage:
    status_np = STATUS_NEPALI[output.decision.status]
    action = STATUS_ACTION_NEPALI[output.decision.status]
    lead = f"{lead_time_minutes:.0f} मिनेट" if lead_time_minutes is not None else "अज्ञात समय"
    body = f"{settlement}: स्थिति {status_np}। पहुँच समय {lead}। {action}"
    return WhatsAppMessage("resident", _prefix(body, replay))


def institutional_message(output: ExplainerOutput, *, replay: bool = False) -> WhatsAppMessage:
    pack = output.evidence_pack
    contributions = "; ".join(pack.contributions)
    refused = "no claim issued on cause" if output.vetoed else "no facts were refused"
    body = (
        f"STATUS {pack.status} (score {pack.score:.2f}). {contributions}. "
        "This is a modelled scenario, not a prediction. "
        f"What was refused: {refused}."
    )
    return WhatsAppMessage("institutional", _prefix(body, replay))


def approver_message(
    output: ExplainerOutput, run_id: str, image_url: str | None, *, replay: bool = False
) -> WhatsAppMessage:
    pack = output.evidence_pack
    counterfactual = pack.counterfactuals[0] if pack.counterfactuals else None
    cf_text = (
        f"If {counterfactual.change}, status would be {counterfactual.new_status}."
        if counterfactual
        else "no counterfactual available."
    )
    flip = "; ".join(pack.flip_point_summary)
    image_note = f" Image: {image_url}." if image_url else ""
    body = (
        f"GATE REQUEST run {run_id}. STATUS {pack.status}. {cf_text} Flip points: {flip}."
        f"{image_note} Reply APPROVE {run_id} to release, or REJECT {run_id}."
    )
    return WhatsAppMessage("approver", _prefix(body, replay))
