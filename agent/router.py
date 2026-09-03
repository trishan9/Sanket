from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

import litellm
from litellm import Router

from agent.budget import Provider, budget
from agent.cache import cache_key, response_cache
from agent.trace import Trace
from core.errors import AllProvidersFailedError, ConfigError

litellm.suppress_debug_info = True
litellm.set_verbose = False

Lane = Literal[
    "sanket-scout",
    "sanket-classify",
    "sanket-explain",
    "sanket-plan",
    "sanket-critic",
    "sanket-voice",
    "sanket-scout-alt",
    "sanket-classify-alt",
    "sanket-explain-alt",
    "sanket-plan-alt",
    "sanket-critic-alt",
]

PRIMARY_LANES: tuple[Lane, ...] = (
    "sanket-scout",
    "sanket-classify",
    "sanket-explain",
    "sanket-plan",
    "sanket-critic",
    "sanket-voice",
)

AZURE_BASE_ENV = "HACKATHON_BASE"
AZURE_KEY_ENV = "HACKATHON_KEY"
GROQ_KEY_ENV = "GROQ_KEY"

AZURE_PLAN = "gpt-5.5"
AZURE_CRITIC = "grok-4.6"
AZURE_VOICE = "gpt-audio"
AZURE_FLASH = "DeepSeek-V4-Flash"
AZURE_PRO = "DeepSeek-V4-Pro"
GROQ_SCOUT = "groq/compound"
GROQ_CLASSIFY = "openai/gpt-oss-20b"
GROQ_EXPLAIN = "openai/gpt-oss-120b"
GROQ_CRITIC = "qwen/qwen3.8-27b"


@dataclass(frozen=True)
class Deployment:
    lane: Lane
    model: str
    provider: Literal["azure", "groq"]
    tpm: int
    rpm: int


DEPLOYMENTS: tuple[Deployment, ...] = (
    Deployment("sanket-scout", GROQ_SCOUT, "groq", 70000, 30),
    Deployment("sanket-scout-alt", AZURE_FLASH, "azure", 30000, 60),
    Deployment("sanket-classify", GROQ_CLASSIFY, "groq", 30000, 30),
    Deployment("sanket-classify-alt", AZURE_FLASH, "azure", 30000, 60),
    Deployment("sanket-explain", GROQ_EXPLAIN, "groq", 20000, 30),
    Deployment("sanket-explain-alt", AZURE_PRO, "azure", 30000, 60),
    Deployment("sanket-plan", AZURE_PLAN, "azure", 30000, 60),
    Deployment("sanket-plan-alt", GROQ_EXPLAIN, "groq", 8000, 30),
    Deployment("sanket-critic", AZURE_CRITIC, "azure", 30000, 60),
    Deployment("sanket-critic-alt", GROQ_CRITIC, "groq", 8000, 30),
    Deployment("sanket-voice", AZURE_VOICE, "azure", 30000, 60),
)

DEPLOYMENT_OF: dict[str, Deployment] = {d.lane: d for d in DEPLOYMENTS}

FALLBACKS: list[dict[str, list[str]]] = [
    {"sanket-plan": ["sanket-plan-alt", "sanket-critic"]},
    {"sanket-plan-alt": ["sanket-explain"]},
    {"sanket-critic": ["sanket-critic-alt", "sanket-plan"]},
    {"sanket-critic-alt": ["sanket-explain"]},
    {"sanket-classify": ["sanket-classify-alt", "sanket-scout"]},
    {"sanket-classify-alt": ["sanket-scout"]},
    {"sanket-explain": ["sanket-explain-alt", "sanket-classify"]},
    {"sanket-explain-alt": ["sanket-classify"]},
    {"sanket-scout": ["sanket-scout-alt", "sanket-classify"]},
    {"sanket-scout-alt": ["sanket-classify"]},
]

DEGRADATION_LADDER: tuple[str, ...] = ("azure", "groq", "deterministic", "last_known_good")


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set; add it to .env")
    return value


def _litellm_params(deployment: Deployment) -> dict[str, Any]:
    if deployment.provider == "azure":
        return {
            "model": f"openai/{deployment.model}",
            "api_base": _require(AZURE_BASE_ENV),
            "api_key": _require(AZURE_KEY_ENV),
        }
    return {"model": f"groq/{deployment.model}", "api_key": _require(GROQ_KEY_ENV)}


def build_model_list() -> list[dict[str, Any]]:
    return [
        {
            "model_name": d.lane,
            "litellm_params": _litellm_params(d),
            "tpm": d.tpm,
            "rpm": d.rpm,
        }
        for d in DEPLOYMENTS
    ]


def qualified_name(lane: str) -> str:
    deployment = DEPLOYMENT_OF.get(lane)
    if deployment is None:
        return lane
    return f"{deployment.provider}/{deployment.model}"


def provider_of_lane(lane: str) -> Provider:
    deployment = DEPLOYMENT_OF.get(lane)
    return deployment.provider if deployment else "deterministic"


def resolve_served(lane: str, response: Any) -> tuple[str, Provider]:
    intended = DEPLOYMENT_OF.get(lane)
    raw = str(getattr(response, "model", "") or "")
    served_model = raw or (intended.model if intended else lane)
    hidden = getattr(response, "_hidden_params", None) or {}
    api_base = str(hidden.get("api_base") or "")
    if "groq.com" in api_base:
        return served_model, "groq"
    if "azure.com" in api_base or "openai.azure" in api_base:
        return served_model, "azure"
    return served_model, provider_of_lane(lane)


def matches_intended(served_model: str, intended_model: str) -> bool:
    return served_model == intended_model or served_model.startswith(f"{intended_model}-")


def build_router() -> Router:
    return Router(
        model_list=build_model_list(),
        routing_strategy="simple-shuffle",
        fallbacks=FALLBACKS,
        num_retries=3,
        allowed_fails=2,
        cooldown_time=60,
        timeout=45,
    )


class Gateway:
    def __init__(self, router: Router | None = None) -> None:
        self._router = router
        self.degradations: list[str] = []

    @property
    def router(self) -> Router:
        if self._router is None:
            self._router = build_router()
        return self._router

    def complete(
        self,
        lane: Lane,
        messages: list[dict[str, Any]],
        *,
        run_id: str,
        trace: Trace | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        use_cache: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        key = cache_key(lane, messages, tools)
        if use_cache:
            cached = response_cache.get(key)
            if cached is not None:
                if trace is not None:
                    trace.emit("STEP", f"cache hit on {lane}", model=qualified_name(lane))
                return cached
        payload = self._call(lane, messages, tools, tool_choice, run_id, trace, **kwargs)
        if use_cache:
            response_cache.put(key, lane, payload)
        return payload

    def _call(
        self,
        lane: Lane,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        run_id: str,
        trace: Trace | None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {"model": lane, "messages": messages, **kwargs}
        if tools:
            request["tools"] = tools
            request["tool_choice"] = tool_choice or "auto"
        try:
            response = self.router.completion(**request)
        except Exception as exc:
            self._record_degradation(lane, exc, trace)
            raise AllProvidersFailedError(f"lane {lane} exhausted: {exc}") from exc
        return self._normalise(lane, response, run_id, trace)

    def _record_degradation(self, lane: Lane, exc: Exception, trace: Trace | None) -> None:
        note = f"{lane}: all deployments failed ({type(exc).__name__})"
        self.degradations.append(note)
        if trace is not None:
            trace.degraded(f"{note} -> deterministic mode")

    def _normalise(
        self, lane: Lane, response: Any, run_id: str, trace: Trace | None
    ) -> dict[str, Any]:
        intended = DEPLOYMENT_OF.get(lane)
        used, provider = resolve_served(lane, response)
        genuinely_intended = intended is not None and (
            matches_intended(used, intended.model) and provider == intended.provider
        )
        if intended is not None and not genuinely_intended:
            note = f"{lane} served by {provider}/{used}, not {intended.provider}/{intended.model}"
            self.degradations.append(note)
            if trace is not None:
                trace.degraded(note)
        usage = getattr(response, "usage", None)
        tokens_in = int(getattr(usage, "prompt_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "completion_tokens", 0) or 0)
        npr = budget.record(run_id, used, tokens_in, tokens_out, provider=provider)
        message = response.choices[0].message
        payload: dict[str, Any] = {
            "lane": lane,
            "model": used,
            "provider": provider,
            "content": message.content,
            "tool_calls": _tool_calls(message),
            "audio_base64": _audio_base64(message),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_npr": npr,
        }
        if trace is not None and payload["content"]:
            trace.emit(
                "STEP",
                str(payload["content"])[:160],
                model=f"{provider}/{used}",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_npr=npr,
            )
        return payload


def _tool_calls(message: Any) -> list[dict[str, Any]]:
    raw = getattr(message, "tool_calls", None) or []
    return [
        {
            "id": call.id,
            "name": call.function.name,
            "arguments": call.function.arguments,
        }
        for call in raw
    ]


def _audio_base64(message: Any) -> str | None:
    audio = getattr(message, "audio", None)
    if audio is None:
        return None
    data = getattr(audio, "data", None)
    return str(data) if data else None


gateway = Gateway()
