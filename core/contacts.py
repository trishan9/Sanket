from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from core.config import paths
from core.errors import ConfigError

Role = Literal[
    "ddmc_duty_officer",
    "dhm_hydrologist",
    "local_administration",
    "hydropower_operator",
    "police_post",
    "health_post",
    "school",
    "community_focal_point",
]

APPROVER_ENV = "APPROVER_WHATSAPP"


class Contact(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    name: str
    channel: Literal["whatsapp", "sms", "voice"]
    contact: str
    settlement: str | None = None
    synthetic: bool = True


class Approver(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["ddmc_duty_officer"] = "ddmc_duty_officer"
    name: str = "DDMC Rasuwa Duty Officer"
    contact: str
    synthetic: bool = False


def load_institutional_contacts(path: Path | None = None) -> tuple[Contact, ...]:
    target = path or (paths.data / "contacts" / "institutional.yml")
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ConfigError(f"institutional contacts file is not a list: {target}")
    return tuple(Contact(**item) for item in raw)


def approver() -> Approver:
    contact = os.environ.get(APPROVER_ENV, "").strip()
    if not contact:
        raise ConfigError(f"{APPROVER_ENV} is not set; add it to .env")
    return Approver(contact=contact)
