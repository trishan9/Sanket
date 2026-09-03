from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb
from smolagents import CodeAgent, Tool
from smolagents.models import ChatMessage, Model

from agent.router import Lane, gateway
from core.config import paths
from core.errors import SandboxError

SANDBOX_LANE: Lane = "sanket-explain"
TIMEOUT_SECONDS = 10
MAX_STEPS = 4
AUTHORIZED_IMPORTS: tuple[str, ...] = ("geopandas", "rasterio", "numpy", "pandas", "shapely")

SANDBOX_PROMPT_PREFIX = (
    "You are a read-only data analyst answering one follow-up question about a glacial-"
    "hazard investigation. You have a DuckDB connection named `lakehouse` (read-only - "
    "writes will fail) over the bronze/silver catalog, and geopandas/rasterio/pandas/"
    "numpy for any file-based analysis. You cannot write status, send a notification or "
    "influence a gate decision - you can only compute and report. Show your Python. "
    "Question: "
)


@dataclass(frozen=True)
class SandboxResult:
    answer: str
    code: str
    claim_type: str = "model_output"


class _GatewayModel(Model):
    def __init__(self, lane: Lane, run_id: str) -> None:
        super().__init__(model_id=lane)
        self._lane = lane
        self._run_id = run_id

    def generate(
        self,
        messages: list[ChatMessage | dict[str, Any]],
        stop_sequences: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools_to_call_from: list[Tool] | None = None,
        **kwargs: Any,
    ) -> ChatMessage:
        prepared = self._prepare_completion_kwargs(
            messages=messages,
            stop_sequences=stop_sequences,
            response_format=response_format,
            tools_to_call_from=tools_to_call_from,
            flatten_messages_as_text=True,
            **kwargs,
        )
        response = gateway.complete(
            self._lane,
            prepared["messages"],
            run_id=self._run_id,
            use_cache=False,
            max_tokens=prepared.get("max_tokens", 1500),
        )
        return ChatMessage(role="assistant", content=response["content"] or "")


def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(paths.lakehouse_db), read_only=True)


def _build_agent(run_id: str) -> CodeAgent:
    model = _GatewayModel(SANDBOX_LANE, run_id)
    return CodeAgent(
        tools=[],
        model=model,
        additional_authorized_imports=list(AUTHORIZED_IMPORTS),
        max_steps=MAX_STEPS,
        executor_kwargs={"timeout_seconds": TIMEOUT_SECONDS},
    )


def _last_code(agent: CodeAgent) -> str:
    for step in reversed(agent.memory.steps):
        code = getattr(step, "code_action", None)
        if code:
            return str(code)
    return ""


def ask(question: str, *, run_id: str = "sandbox") -> SandboxResult:
    agent = _build_agent(run_id)
    connection = _connection()
    try:
        answer = agent.run(
            SANDBOX_PROMPT_PREFIX + question, additional_args={"lakehouse": connection}
        )
    except Exception as exc:
        raise SandboxError(f"sandbox query failed: {exc}") from exc
    finally:
        connection.close()
    return SandboxResult(answer=str(answer), code=_last_code(agent))
