from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from actions import gate, subscribers, templates_wa
from actions.alertcard import render_alert_card
from actions.channels.base import DeliveryResult
from actions.channels.twilio_whatsapp import TwilioWhatsApp
from agent.explainer import ExplainerOutput
from core.config import settings
from core.contacts import approver, load_institutional_contacts
from core.corridor import Corridor
from core.errors import CooldownActiveError
from core.state import State

FALLBACK_MAP_IMAGE_URL = (
    "https://vantor-opendata.s3.amazonaws.com/events/Nepal-Flooding-Aug-2026/10500100364E8400.jpg"
)


def card_url(filename: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/alertcards/{filename}"


def build_card_url(
    corridor: Corridor | None,
    settlement: str,
    level: str,
    run_id: str,
    lead_time_minutes: float | None,
    replay: bool,
) -> str:
    if corridor is None:
        return FALLBACK_MAP_IMAGE_URL
    card = render_alert_card(
        corridor,
        settlement,
        level,
        run_id,
        lead_time_minutes=lead_time_minutes,
        replay=replay,
    )
    return card_url(card.path.name)


@dataclass(frozen=True)
class SendOutcome:
    tier: str
    contact: str
    settlement: str
    result: DeliveryResult
    notification_id: str


def _draft_payload(
    output: ExplainerOutput,
    settlement_lead_times: dict[str, float | None],
    replay: bool,
    corridor: Corridor | None,
    run_id: str,
) -> dict[str, Any]:
    institutional = templates_wa.institutional_message(output, replay=replay)
    resident = {
        settlement: templates_wa.resident_message(output, settlement, lead, replay=replay).body
        for settlement, lead in settlement_lead_times.items()
    }
    status = output.decision.status
    resident_images = {
        settlement: build_card_url(corridor, settlement, status, run_id, lead, replay)
        for settlement, lead in settlement_lead_times.items()
    }
    first = next(iter(settlement_lead_times), "")
    pack = output.evidence_pack
    return {
        "status": status,
        "institutional_body": institutional.body,
        "resident_bodies": resident,
        "resident_images": resident_images,
        "image_url": resident_images.get(first, FALLBACK_MAP_IMAGE_URL),
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
        "provenance_links": list(pack.provenance_links),
    }


def send_gate_request(
    output: ExplainerOutput,
    run_id: str,
    settlement_lead_times: dict[str, float | None],
    *,
    replay: bool = False,
    store: State | None = None,
    corridor: Corridor | None = None,
) -> tuple[gate.GateRecord, SendOutcome]:
    payload = _draft_payload(output, settlement_lead_times, replay, corridor, run_id)
    record = gate.request_gate(
        run_id,
        "release_alert",
        payload=payload,
        evidence_snapshot={"provenance_links": list(output.evidence_pack.provenance_links)},
        store=store,
    )
    image_url = str(payload["image_url"])
    message = templates_wa.approver_message(output, run_id, image_url, replay=replay)
    contact = approver().contact
    result = TwilioWhatsApp().send_media(contact, message.body, image_url)
    notification_id = gate.record_notification(
        "gate",
        "whatsapp",
        contact,
        run_id,
        result.status,
        store=store,
        message_sid=result.message_sid or None,
    )
    return record, SendOutcome("approver", contact, "gate", result, notification_id)


def _send_institutional(
    body: str, run_id: str, channel: TwilioWhatsApp, store: State | None
) -> list[SendOutcome]:
    outcomes: list[SendOutcome] = []
    for contact in load_institutional_contacts():
        key = f"institutional:{contact.role}"
        try:
            gate.check_cooldown(key, "whatsapp", store=store)
        except CooldownActiveError:
            continue
        result = channel.send_text(contact.contact, body)
        notification_id = gate.record_notification(
            key,
            "whatsapp",
            contact.contact,
            run_id,
            result.status,
            store=store,
            message_sid=result.message_sid or None,
        )
        outcomes.append(SendOutcome("institutional", contact.contact, key, result, notification_id))
    return outcomes


def _send_residents(
    resident_bodies: dict[str, str],
    image_url: str,
    run_id: str,
    channel: TwilioWhatsApp,
    store: State | None,
    resident_images: dict[str, str] | None = None,
) -> list[SendOutcome]:
    outcomes: list[SendOutcome] = []
    images = resident_images or {}
    for settlement, body in resident_bodies.items():
        try:
            gate.check_cooldown(settlement, "whatsapp", store=store)
        except CooldownActiveError:
            continue
        media = images.get(settlement, image_url)
        for contact in subscribers.list_subscribers(settlement, "whatsapp", store=store):
            result = channel.send_media(contact, body, media)
            notification_id = gate.record_notification(
                settlement,
                "whatsapp",
                contact,
                run_id,
                result.status,
                store=store,
                message_sid=result.message_sid or None,
            )
            outcomes.append(SendOutcome("resident", contact, settlement, result, notification_id))
    return outcomes


def release_from_gate(record: gate.GateRecord, store: State | None = None) -> list[SendOutcome]:
    channel = TwilioWhatsApp()
    payload = record.payload
    outcomes = _send_institutional(payload["institutional_body"], record.run_id, channel, store)
    outcomes += _send_residents(
        payload["resident_bodies"],
        payload["image_url"],
        record.run_id,
        channel,
        store,
        payload.get("resident_images"),
    )
    return outcomes
