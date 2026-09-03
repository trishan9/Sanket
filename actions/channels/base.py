from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryResult:
    message_sid: str
    status: str
    to: str
    error: str | None = None


class Channel(ABC):
    @abstractmethod
    def send_text(self, to: str, body: str) -> DeliveryResult: ...

    @abstractmethod
    def send_media(self, to: str, body: str, media_url: str) -> DeliveryResult: ...
