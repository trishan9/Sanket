from __future__ import annotations

import pathlib
import tempfile
from datetime import UTC, datetime, timedelta

import pytest

from actions import gate, scripts_ne, sms, subscribers, templates_wa
from actions.actor import act
from agent.decision import Contribution, Decision
from agent.explainer import EvidencePack, ExplainerOutput, PublicNote, ResidentScript
from core.contacts import approver, load_institutional_contacts
from core.errors import CooldownActiveError, GateNotApprovedError, UnauthorisedApproverError
from core.state import State


@pytest.fixture
def store() -> State:
    return State(pathlib.Path(tempfile.mkdtemp()) / "t.sqlite")


def _output(status: str, score: float = 0.5) -> ExplainerOutput:
    decision = Decision(
        status,  # type: ignore[arg-type]
        score,
        (Contribution("change magnitude", "z=3.40", 0.4, 0.4),),
    )
    pack = EvidencePack(
        status=status,  # type: ignore[arg-type]
        score=score,
        contributions=("change magnitude z=3.40 contribution +0.400",),
        counterfactuals=(),
        flip_point_summary=(),
        what_would_change_my_mind=("no open evidence gaps recorded against this ledger",),
        provenance_links=("ev_abc123",),
    )
    note = PublicNote(english=f"Status: {status}.", nepali=f"स्थिति: {status}।")
    scripts = (ResidentScript("Timure", f"Timure: स्थिति {status}।"),)
    return ExplainerOutput(decision, status == "INSUFFICIENT", pack, note, scripts)


def test_institutional_contacts_load_and_are_declared_synthetic() -> None:
    contacts = load_institutional_contacts()
    assert len(contacts) == 7
    assert all(c.synthetic for c in contacts)


def test_approver_is_not_synthetic() -> None:
    assert approver().synthetic is False
    assert approver().contact.startswith("whatsapp:")


def test_gate_request_and_unauthorized_approval_rejected(store: State) -> None:
    gate.request_gate("run_a", "release_alert", {}, {}, store=store)
    with pytest.raises(UnauthorisedApproverError):
        gate.record_decision(
            "run_a", "whatsapp:+9779999999999", approver().contact, "approved", store=store
        )


def test_gate_approval_by_registered_approver_succeeds(store: State) -> None:
    gate.request_gate("run_b", "release_alert", {}, {}, store=store)
    record = gate.record_decision(
        "run_b", approver().contact, approver().contact, "approved", store=store
    )
    assert record.decision == "approved"
    assert record.approver == approver().contact


def test_gate_decision_on_nonexistent_run_raises(store: State) -> None:
    with pytest.raises(GateNotApprovedError):
        gate.record_decision(
            "no_such_run", approver().contact, approver().contact, "approved", store=store
        )


def test_expired_gate_cannot_be_approved(store: State) -> None:
    record = gate.request_gate("run_c", "release_alert", {}, {}, store=store)
    with store._lock, store.connect() as connection:
        connection.execute(
            "UPDATE gates SET deadline=? WHERE gate_id=?",
            ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), record.gate_id),
        )
    with pytest.raises(GateNotApprovedError):
        gate.record_decision(
            "run_c", approver().contact, approver().contact, "approved", store=store
        )


def test_cooldown_blocks_a_second_message_inside_the_window(store: State) -> None:
    gate.record_notification(
        "Timure", "whatsapp", "whatsapp:+9770000", "run_d", "sent", store=store
    )
    with pytest.raises(CooldownActiveError):
        gate.check_cooldown("Timure", "whatsapp", store=store)


def test_cooldown_absent_for_a_settlement_never_notified(store: State) -> None:
    gate.check_cooldown("Dhunche", "whatsapp", store=store)


def test_stop_unsubscribes_and_is_honoured_before_next_send(store: State) -> None:
    contact = "whatsapp:+9771234567"
    subscribers.opt_in(contact, "whatsapp", "Timure", "resident", store=store)
    assert subscribers.list_subscribers("Timure", "whatsapp", store=store) == (contact,)
    subscribers.stop(contact, "whatsapp", store=store)
    assert subscribers.list_subscribers("Timure", "whatsapp", store=store) == ()


def test_sms_stays_within_140_characters() -> None:
    text = scripts_ne.sms_text("Trishuli Bazaar", "चेतावनी", 240)
    assert len(text) <= scripts_ne.SMS_MAX_CHARS


def test_sms_draft_is_marked_simulated_not_a_real_send() -> None:
    output = _output("WATCH")
    draft = sms.draft(output, "Timure", 14)
    assert draft.simulated is True
    assert "Timure" in draft.body


def test_voice_script_contains_settlement_and_lead_time_slots() -> None:
    text = scripts_ne.voice_script("Timure", 14)
    assert "Timure" in text
    assert "14" in text


def test_three_registers_agree_on_status_word() -> None:
    output = _output("ALERT")
    resident = templates_wa.resident_message(output, "Timure", 14)
    institutional = templates_wa.institutional_message(output)
    approver_msg = templates_wa.approver_message(output, "run_x", None)
    assert "ALERT" in institutional.body
    assert "ALERT" in approver_msg.body
    from agent.explainer import STATUS_NEPALI

    assert STATUS_NEPALI["ALERT"] in resident.body


def test_replay_prefix_applied_to_all_tiers() -> None:
    output = _output("WATCH")
    resident = templates_wa.resident_message(output, "Timure", 14, replay=True)
    institutional = templates_wa.institutional_message(output, replay=True)
    approver_msg = templates_wa.approver_message(output, "run_x", None, replay=True)
    for message in (resident, institutional, approver_msg):
        assert message.body.startswith(templates_wa.REPLAY_PREFIX)


def test_watch_writes_autonomously_and_the_board_changes(store: State) -> None:
    output = _output("WATCH")
    result = act(output, "Timure", "bhotekoshi_trishuli", "run_watch", {"Timure": 14}, store=store)
    assert result["autonomous"] is True
    board = store.statuses("bhotekoshi_trishuli")
    assert board[0]["level"] == "WATCH"


def test_insufficient_also_writes_autonomously(store: State) -> None:
    output = _output("INSUFFICIENT", score=0.0)
    result = act(
        output, "Timure", "bhotekoshi_trishuli", "run_insufficient", {"Timure": 14}, store=store
    )
    assert result["autonomous"] is True


@pytest.mark.network
def test_alert_stops_at_the_gate_with_no_board_write(store: State) -> None:
    output = _output("ALERT", score=0.8)
    result = act(
        output, "Timure", "bhotekoshi_trishuli", "run_alert_gate", {"Timure": 14}, store=store
    )
    assert result["autonomous"] is False
    assert result["gate_id"]
    assert store.statuses("bhotekoshi_trishuli") == []


@pytest.mark.network
def test_gate_request_approve_and_release_cycle_is_real(store: State) -> None:
    from actions import inbound
    from actions.whatsapp import send_gate_request

    output = _output("ALERT", score=0.8)
    approver_contact = approver().contact
    subscribers.opt_in(approver_contact, "whatsapp", "Timure", "resident", store=store)

    record, outcome = send_gate_request(output, "run_cycle", {"Timure": 14}, store=store)
    assert record.decision == "pending"
    assert outcome.result.status != "failed"
    assert outcome.result.message_sid

    unauthorized = inbound.handle_inbound(
        "whatsapp:+9779999999999", "APPROVE run_cycle", store=store
    )
    assert unauthorized["action"] == "unauthorised"

    approved = inbound.handle_inbound(approver_contact, "APPROVE run_cycle", store=store)
    assert approved["action"] == "approved"
    assert approved["released"] >= 8

    with store.connect() as connection:
        rows = connection.execute(
            "SELECT settlement, delivery_status, message_sid FROM notifications "
            "WHERE run_id='run_cycle'"
        ).fetchall()
    resident_rows = [r for r in rows if r["settlement"] == "Timure"]
    assert resident_rows
    assert resident_rows[0]["message_sid"]


@pytest.mark.network
def test_delivery_status_written_back_to_notifications(store: State) -> None:
    from actions.inbound import handle_status_callback

    notification_id = gate.record_notification(
        "Dhunche",
        "whatsapp",
        "whatsapp:+9779800000006",
        "run_status",
        "queued",
        store=store,
        message_sid="SMtestfakestatus123",
    )
    updated = handle_status_callback("SMtestfakestatus123", "delivered", store=store)
    assert updated is True
    with store.connect() as connection:
        row = connection.execute(
            "SELECT delivery_status FROM notifications WHERE notification_id=?",
            (notification_id,),
        ).fetchone()
    assert row["delivery_status"] == "delivered"


@pytest.mark.network
def test_real_nepali_voice_audio_is_generated() -> None:
    from actions.voice import generate_call

    result = generate_call("Timure", 14, "run_voice_test")
    audio_path = pathlib.Path(result.audio_path)
    assert audio_path.exists()
    assert audio_path.stat().st_size > 10_000
    header = audio_path.read_bytes()[:4]
    assert header == b"RIFF"
    audio_path.unlink()
