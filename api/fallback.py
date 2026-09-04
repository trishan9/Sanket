from __future__ import annotations

from typing import Any

from flask import Response

from actions.board import board_snapshot

STATUS_LABEL_NE: dict[str, str] = {
    "NORMAL": "सामान्य",
    "WATCH": "निगरानी",
    "ALERT": "चेतावनी",
    "INSUFFICIENT": "अपर्याप्त प्रमाण",
}


def _row(settlement: dict[str, Any]) -> str:
    level = settlement["level"]
    lead = settlement["lead_time_minutes"]
    lead_text = f"{round(lead)}min" if lead is not None else "-"
    return f"{settlement['settlement']}: {level} / {STATUS_LABEL_NE.get(level, '-')} ({lead_text})"


def fallback_page() -> Response:
    snapshot = board_snapshot()
    rows = "\n".join(_row(s) for s in snapshot["settlements"])
    body = (
        "SANKET - standing watch (text fallback)\n"
        f"Corridor status: {snapshot['corridor_level']}\n"
        f"Last checked: {snapshot['last_checked']}\n\n"
        f"{rows}\n\n"
        "Full board: /  (needs a faster connection)\n"
        f"Generated: {snapshot['generated_at']}\n"
    )
    return Response(body, mimetype="text/plain; charset=utf-8")
