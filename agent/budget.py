from __future__ import annotations

import re
import threading
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict

from core.config import settings

Provider = Literal["azure", "groq", "local", "deterministic"]


class Price(BaseModel):
    model_config = ConfigDict(frozen=True)

    usd_per_m_input: float
    usd_per_m_output: float


PRICING: dict[str, Price] = {
    "gpt-5.5": Price(usd_per_m_input=1.25, usd_per_m_output=10.0),
    "grok-4.6": Price(usd_per_m_input=3.0, usd_per_m_output=15.0),
    "gpt-audio": Price(usd_per_m_input=2.5, usd_per_m_output=10.0),
    "DeepSeek-V4-Flash": Price(usd_per_m_input=0.14, usd_per_m_output=0.28),
    "DeepSeek-V4-Pro": Price(usd_per_m_input=0.27, usd_per_m_output=1.10),
    "groq/compound": Price(usd_per_m_input=0.15, usd_per_m_output=0.60),
    "openai/gpt-oss-20b": Price(usd_per_m_input=0.10, usd_per_m_output=0.50),
    "openai/gpt-oss-120b": Price(usd_per_m_input=0.15, usd_per_m_output=0.75),
    "qwen/qwen3.8-27b": Price(usd_per_m_input=0.29, usd_per_m_output=0.59),
}

COUNTERFACTUAL_MODEL = "gpt-5.5"


def provider_of(model: str) -> Provider:
    bare = model.split("/", 1)[-1] if model.startswith(("azure/", "groq/")) else model
    if model.startswith("groq/") or bare.startswith(("groq", "openai/gpt-oss", "qwen/")):
        return "groq"
    if model.startswith("azure/") or bare in PRICING:
        return "azure"
    if model.startswith("ollama/"):
        return "local"
    return "deterministic"


DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def _strip_date_suffix(model: str) -> str:
    return DATE_SUFFIX.sub("", model)


def _lookup(model: str) -> Price | None:
    stripped = model.removeprefix("azure/").removeprefix("groq/").removeprefix("openai/")
    for candidate in (model, stripped, _strip_date_suffix(model), _strip_date_suffix(stripped)):
        if candidate in PRICING:
            return PRICING[candidate]
    bare = _strip_date_suffix(stripped)
    for key, price in PRICING.items():
        if key.rsplit("/", 1)[-1] == bare:
            return price
    return None


def cost_npr(model: str, tokens_in: int, tokens_out: int) -> float:
    price = _lookup(model)
    if price is None:
        return 0.0
    usd = (tokens_in / 1e6) * price.usd_per_m_input + (tokens_out / 1e6) * price.usd_per_m_output
    return usd * settings.npr_per_usd


class RunBudget(BaseModel):
    run_id: str
    tokens_in: dict[str, int] = {}
    tokens_out: dict[str, int] = {}
    cost_npr: dict[str, float] = {}
    calls: dict[str, int] = {}
    counterfactual_npr: float = 0.0

    @property
    def total_npr(self) -> float:
        return sum(self.cost_npr.values())

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens_in.values()) + sum(self.tokens_out.values())

    def summary(self) -> str:
        parts = " · ".join(f"{p} {v:.2f}" for p, v in sorted(self.cost_npr.items()))
        return f"NPR {self.total_npr:.2f} ({parts})"


class Budget:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, RunBudget] = {}

    def record(
        self,
        run_id: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        provider: Provider | None = None,
    ) -> float:
        provider = provider or provider_of(model)
        npr = cost_npr(model, tokens_in, tokens_out)
        counterfactual = cost_npr(COUNTERFACTUAL_MODEL, tokens_in, tokens_out)
        with self._lock:
            run = self._runs.setdefault(run_id, RunBudget(run_id=run_id))
            run.tokens_in[provider] = run.tokens_in.get(provider, 0) + tokens_in
            run.tokens_out[provider] = run.tokens_out.get(provider, 0) + tokens_out
            run.cost_npr[provider] = run.cost_npr.get(provider, 0.0) + npr
            run.calls[provider] = run.calls.get(provider, 0) + 1
            run.counterfactual_npr += counterfactual
        return npr

    def get(self, run_id: str) -> RunBudget:
        with self._lock:
            return self._runs.get(run_id, RunBudget(run_id=run_id)).model_copy(deep=True)

    def totals(self) -> dict[str, float]:
        with self._lock:
            out: dict[str, float] = defaultdict(float)
            for run in self._runs.values():
                for provider, value in run.cost_npr.items():
                    out[provider] += value
            return dict(out)


budget = Budget()
