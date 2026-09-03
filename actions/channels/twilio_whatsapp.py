from __future__ import annotations

import os
from typing import Any

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from actions.channels.base import Channel, DeliveryResult
from core.errors import ConfigError

ACCOUNT_SID_ENV = "TWILIO_ACCOUNT_SID"
AUTH_TOKEN_ENV = "TWILIO_AUTH_TOKEN"
FROM_ENV = "TWILIO_WHATSAPP_FROM"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set; add it to .env")
    return value


class TwilioWhatsApp(Channel):
    def __init__(self) -> None:
        self._client = Client(_require(ACCOUNT_SID_ENV), _require(AUTH_TOKEN_ENV))
        self._from = _require(FROM_ENV)

    def send_text(self, to: str, body: str) -> DeliveryResult:
        return self._send(to, body, media_url=None)

    def send_media(self, to: str, body: str, media_url: str) -> DeliveryResult:
        return self._send(to, body, media_url=media_url)

    def _send(self, to: str, body: str, media_url: str | None) -> DeliveryResult:
        kwargs: dict[str, Any] = {"from_": self._from, "to": to, "body": body}
        if media_url:
            kwargs["media_url"] = [media_url]
        try:
            message = self._client.messages.create(**kwargs)
        except TwilioRestException as exc:
            return DeliveryResult("", "failed", to, error=str(exc))
        return DeliveryResult(message.sid, message.status, to)
