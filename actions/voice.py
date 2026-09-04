from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from actions.scripts_ne import voice_script
from agent.router import Lane, gateway
from agent.trace import Trace
from core.config import paths
from core.errors import DeliveryFailedError

VOICE_LANE: Lane = "sanket-voice"
VOICE_NAME = "alloy"
AUDIO_FORMAT = "wav"


@dataclass(frozen=True)
class VoiceCallResult:
    settlement: str
    script: str
    audio_path: str
    dialler_simulated: bool = True


STREAMING_PLACEHOLDER = 0xFFFFFFFF


def _with_real_sizes(raw: bytes) -> bytes:
    if len(raw) < 44 or raw[:4] != b"RIFF":
        return raw
    data_at = raw.find(b"data")
    if data_at == -1:
        return raw
    patched = bytearray(raw)
    if int.from_bytes(patched[4:8], "little") == STREAMING_PLACEHOLDER:
        patched[4:8] = (len(raw) - 8).to_bytes(4, "little")
    payload = data_at + 8
    if int.from_bytes(patched[payload - 4 : payload], "little") == STREAMING_PLACEHOLDER:
        patched[payload - 4 : payload] = (len(raw) - payload).to_bytes(4, "little")
    return bytes(patched)


def _audio_path(settlement: str, run_id: str) -> Path:
    paths.audio.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{settlement}|{run_id}".encode()).hexdigest()[:12]
    return paths.audio / f"{digest}.{AUDIO_FORMAT}"


def generate_call(
    settlement: str,
    lead_time_minutes: float | None,
    run_id: str,
    trace: Trace | None = None,
) -> VoiceCallResult:
    script = voice_script(settlement, lead_time_minutes)
    response = gateway.complete(
        VOICE_LANE,
        [{"role": "user", "content": f"Say exactly this in Nepali, natural pace: {script}"}],
        run_id=run_id,
        trace=trace,
        use_cache=False,
        modalities=["text", "audio"],
        audio={"voice": VOICE_NAME, "format": AUDIO_FORMAT},
    )
    audio_base64 = response.get("audio_base64")
    if not audio_base64:
        raise DeliveryFailedError(f"{VOICE_LANE} returned no audio for {settlement}")
    target = _audio_path(settlement, run_id)
    target.write_bytes(_with_real_sizes(base64.b64decode(audio_base64)))
    return VoiceCallResult(settlement=settlement, script=script, audio_path=str(target))


def call_summary(result: VoiceCallResult) -> dict[str, object]:
    return {
        "settlement": result.settlement,
        "script": result.script,
        "audio_path": result.audio_path,
        "dialler_simulated": result.dialler_simulated,
        "generated_at": datetime.now(UTC).isoformat(),
    }
