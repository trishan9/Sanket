from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from actions.gate import record_notification
from actions.scripts_ne import sms_text
from agent.explainer import STATUS_NEPALI, ExplainerOutput
from core.state import State

SIMULATED_GATEWAY = "simulated-sms-gateway"


@dataclass(frozen=True)
class SmsDraft:
    settlement: str
    contact: str
    body: str
    simulated: bool = True
    sent_at: str = ""


def draft(output: ExplainerOutput, settlement: str, lead_time_minutes: float | None) -> SmsDraft:
    status_np = STATUS_NEPALI[output.decision.status]
    body = sms_text(settlement, status_np, lead_time_minutes)
    return SmsDraft(settlement=settlement, contact="", body=body)


def send_simulated(
    draft_message: SmsDraft, contact: str, run_id: str, store: State | None = None
) -> str:
    return record_notification(
        draft_message.settlement, "sms", contact, run_id, "simulated", store=store
    )


def summary(draft_message: SmsDraft) -> dict[str, object]:
    return {
        "settlement": draft_message.settlement,
        "body": draft_message.body,
        "chars": len(draft_message.body),
        "gateway": SIMULATED_GATEWAY,
        "generated_at": datetime.now(UTC).isoformat(),
    }
