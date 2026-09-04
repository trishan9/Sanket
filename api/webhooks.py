from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from flask import Response, jsonify, request

from actions import gate as gate_module
from actions.inbound import handle_inbound, handle_status_callback

EMPTY_TWIML = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"
ASK_TIMEOUT_SECONDS = 60

ASK_SCRIPT = (
    "import json, sys\n"
    "from agent.sandbox import ask\n"
    "result = ask(sys.argv[1])\n"
    "print(json.dumps({'answer': result.answer, 'code': result.code, "
    "'claim_type': result.claim_type}))\n"
)


def twilio_inbound() -> Any:
    from_contact = request.form.get("From", "")
    body = request.form.get("Body", "")
    handle_inbound(from_contact, body)
    return Response(EMPTY_TWIML, mimetype="text/xml")


def twilio_status_callback() -> Any:
    message_sid = request.form.get("MessageSid", "")
    status = request.form.get("MessageStatus", "")
    if message_sid and status:
        handle_status_callback(message_sid, status)
    return "", 204


def gate_screen(run_id: str) -> Any:
    record = gate_module.pending_gate_for_run(run_id)
    if record is None:
        return jsonify({"run_id": run_id, "gate": None})
    return jsonify(
        {
            "run_id": run_id,
            "gate_id": record.gate_id,
            "decision": record.decision,
            "requested_at": record.requested_at.isoformat(),
            "deadline": record.deadline.isoformat(),
            "payload": record.payload,
        }
    )


def ask_sandbox() -> Any:
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    try:
        completed = subprocess.run(
            [sys.executable, "-c", ASK_SCRIPT, question],
            capture_output=True,
            text=True,
            timeout=ASK_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return jsonify({"error": exc.stderr[-2000:] or str(exc)}), 502
    except subprocess.TimeoutExpired:
        return jsonify({"error": f"sandbox query exceeded {ASK_TIMEOUT_SECONDS}s"}), 504
    return jsonify(json.loads(completed.stdout.strip().splitlines()[-1]))
