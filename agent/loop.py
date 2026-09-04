from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from agent.deterministic import run_deterministic_investigation
from agent.ledger import Ledger
from agent.router import Lane, gateway
from agent.tools.catalog import DISPATCH, ToolContext
from agent.tools.schemas import ALL_SCHEMAS, GATED_TOOLS
from agent.trace import Trace
from core.corridor import Corridor
from core.errors import (
    AllProvidersFailedError,
    ClaimNotInLedgerError,
    SanketError,
    StepLimitReachedError,
)
from core.provenance import CLAIM_TYPES
from core.state import State
from core.state import state as default_state

INVESTIGATOR_LANE: Lane = "sanket-plan"
MAX_STEPS = 10
TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)

CONTROL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "propose_claim",
            "description": (
                "Propose a claim to the ledger, citing evidence refs already returned by "
                "earlier tool calls. Checked for evidence licensing before being recorded."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                    "supporting_refs": {"type": "array", "items": {"type": "string"}},
                    "contradicting_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["statement", "claim_type", "supporting_refs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "conclude",
            "description": (
                "Conclude the investigation with a summary. Call only after proposing at "
                "least one claim."
            ),
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": (
                "Stop without concluding and escalate to a human, for example when the "
                "evidence is insufficient or ambiguous."
            ),
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]

INVESTIGATOR_SYSTEM_PROMPT = (
    "You are Investigator. You characterise one glacial-hazard anomaly at a single watched "
    "feature. Goal: characterise the anomaly. Determine whether it represents an impoundment. "
    "If so, determine the downstream consequence and the exposed population. Establish "
    "confidence. Do not state anything the evidence does not support.\n\n"
    "You choose your own tools, in your own order, up to ten iterations. Nothing about the "
    "order is hardcoded. The tools compute every number; you never compute a number yourself, "
    "you only choose which function to call, with what arguments, and interpret what comes "
    "back.\n\n"
    "Rules: you may not state that an outburst is likely or imminent - this imagery cannot "
    "establish that. You may not attribute anything to climate change. All routing outputs "
    "are scenario claims, never predictions. You must report that the DEM predates the event "
    "when you use route_flood or breach_hydrograph. Three gated tools (voice_call, send_sms, "
    "send_whatsapp) may be requested but will never be executed by you; a human must approve "
    "them.\n\n"
    "You communicate findings only through propose_claim, citing evidence refs returned by "
    "your tool calls. When you have enough evidence, call conclude with a summary. If the "
    "evidence is insufficient or contradictory, call escalate with a reason instead of "
    "guessing."
)


def _goal_prompt(
    corridor: Corridor, feature_id: str, anomaly_id: str, trigger: dict[str, Any]
) -> str:
    feature = corridor.feature(feature_id)
    return (
        f"Anomaly {anomaly_id} at watched feature '{feature_id}' ({feature.type}) in "
        f"{corridor.name}, location lon={feature.location[0]}, lat={feature.location[1]}. "
        f"Downstream settlements: {', '.join(corridor.settlement_names)}. "
        f"Trigger context: {json.dumps(trigger)}."
    )


def _current_as_of(corridor: Corridor) -> date:
    if corridor.mode == "replay" and corridor.replay is not None:
        return date.fromisoformat(corridor.replay.clock_start[:10])
    return datetime.now(UTC).date()


def _tool_calls_for_message(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": call["id"],
            "type": "function",
            "function": {"name": call["name"], "arguments": call["arguments"]},
        }
        for call in tool_calls
    ]


def _parse_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_tool_call(
    name: str,
    args: dict[str, Any],
    ctx: ToolContext,
    ledger: Ledger,
    trace: Trace,
    step: int,
) -> str:
    if name in GATED_TOOLS:
        trace.gate(f"step {step}: requested gated tool {name}, not executed autonomously")
        return json.dumps(
            {"status": "gated", "note": f"{name} requires human approval and was not executed"}
        )
    fn = DISPATCH.get(name)
    if fn is None:
        return json.dumps({"status": "error", "note": f"unknown tool {name}"})
    try:
        evidence = _dispatch_with_backoff(fn, name, args, ctx, trace)
    except (SanketError, KeyError, ValueError) as exc:
        trace.tool(name, args, f"error: {type(exc).__name__}: {exc}")
        return json.dumps({"status": "error", "note": f"{type(exc).__name__}: {exc}"})
    evidence = ledger.add(evidence)
    trace.tool(name, args, f"ref={evidence.ref} claim_type={evidence.claim_type}")
    return json.dumps({"ref": evidence.ref, "claim_type": evidence.claim_type, **evidence.value})


def _dispatch_with_backoff(
    fn: Any, name: str, args: dict[str, Any], ctx: ToolContext, trace: Trace
) -> Any:
    attempts = 0
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=8),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
        reraise=True,
    ):
        with attempt:
            attempts += 1
            if attempts > 1:
                trace.retry(name, f"retry {attempts} after transient error")
            return fn(args, ctx)
    raise RuntimeError("unreachable")


def _propose_claim(
    args: dict[str, Any], ledger: Ledger, trace: Trace, step: int
) -> tuple[str, bool]:
    try:
        claim = ledger.propose_claim(
            args.get("statement", ""),
            args.get("claim_type", "hypothesis"),
            args.get("supporting_refs", []),
            contradicting_refs=args.get("contradicting_refs"),
        )
    except ClaimNotInLedgerError as exc:
        return json.dumps({"status": "error", "note": str(exc)}), False
    trace.step(
        step,
        f"proposed claim ({claim.confidence}): {claim.statement}",
        extra={
            "claim_type": claim.claim_type,
            "supporting": [ref.ref for ref in claim.supporting],
            "contradicting": [ref.ref for ref in claim.contradicting],
            "vetoed": claim.vetoed,
        },
    )
    return (
        json.dumps(
            {
                "status": "vetoed" if claim.vetoed else "accepted",
                "confidence": claim.confidence,
                "veto_reason": claim.veto_reason,
            }
        ),
        False,
    )


def _run_control_call(
    name: str, args: dict[str, Any], ledger: Ledger, trace: Trace, step: int
) -> tuple[str, bool]:
    if name == "propose_claim":
        return _propose_claim(args, ledger, trace, step)
    if name == "conclude":
        if not ledger.claims:
            return (
                json.dumps({"status": "error", "note": "propose at least one claim first"}),
                False,
            )
        ledger.conclude(args.get("summary"))
        trace.done(f"investigation concluded: {args.get('summary', '')[:120]}")
        return json.dumps({"status": "concluded"}), True
    if name == "escalate":
        ledger.escalate(None, args.get("reason", ""))
        trace.done(f"investigation escalated: {args.get('reason', '')[:120]}")
        return json.dumps({"status": "escalated"}), True
    return json.dumps({"status": "error", "note": f"unknown control call {name}"}), False


def _run_calls(
    step: int,
    calls: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    ctx: ToolContext,
    ledger: Ledger,
    trace: Trace,
) -> bool:
    finished = False
    for call in calls:
        name = call["name"]
        args = _parse_arguments(call["arguments"])
        if name in ("propose_claim", "conclude", "escalate"):
            content, terminal = _run_control_call(name, args, ledger, trace, step)
            finished = finished or terminal
        else:
            content = _run_tool_call(name, args, ctx, ledger, trace, step)
        messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})
    return finished


def _run_step(
    step: int,
    messages: list[dict[str, Any]],
    schemas: list[dict[str, Any]],
    ctx: ToolContext,
    ledger: Ledger,
    run_id: str,
    trace: Trace,
) -> bool:
    response = gateway.complete(
        INVESTIGATOR_LANE,
        messages,
        run_id=run_id,
        trace=trace,
        tools=schemas,
        tool_choice="auto",
        use_cache=False,
        max_tokens=1200,
    )
    calls = response["tool_calls"]
    if not calls:
        messages.append({"role": "assistant", "content": response["content"] or ""})
        messages.append(
            {"role": "user", "content": "Call a tool, propose_claim, conclude, or escalate."}
        )
        return False

    messages.append(
        {
            "role": "assistant",
            "content": response["content"] or "",
            "tool_calls": _tool_calls_for_message(calls),
        }
    )
    return _run_calls(step, calls, messages, ctx, ledger, trace)


def _schemas_for(tool_names: tuple[str, ...] | None) -> list[dict[str, Any]]:
    if tool_names is None:
        return ALL_SCHEMAS + CONTROL_SCHEMAS
    allowed = set(tool_names)
    selected = [s for s in ALL_SCHEMAS if s["function"]["name"] in allowed]
    return selected + CONTROL_SCHEMAS


def investigate(
    corridor: Corridor,
    anomaly_id: str,
    feature_id: str,
    trigger: dict[str, Any],
    run_id: str,
    trace: Trace,
    store: State | None = None,
    as_of: date | None = None,
    max_steps: int = MAX_STEPS,
    tool_names: tuple[str, ...] | None = None,
    system_prompt: str | None = None,
    deterministic: bool = False,
) -> Ledger:
    target = store or default_state
    effective_as_of = as_of or _current_as_of(corridor)
    ledger = Ledger(run_id, effective_as_of)
    ctx = ToolContext(run_id, effective_as_of, target)
    if deterministic:
        run_deterministic_investigation(corridor, feature_id, ctx, ledger, trace)
        return ledger
    schemas = _schemas_for(tool_names)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt or INVESTIGATOR_SYSTEM_PROMPT},
        {"role": "user", "content": _goal_prompt(corridor, feature_id, anomaly_id, trigger)},
    ]

    for step in range(1, max_steps + 1):
        try:
            if _run_step(step, messages, schemas, ctx, ledger, run_id, trace):
                return ledger
        except AllProvidersFailedError:
            run_deterministic_investigation(corridor, feature_id, ctx, ledger, trace)
            return ledger

    try:
        _ = ledger.outcome
    except StepLimitReachedError:
        ledger.escalate(None, f"MAX_STEPS={max_steps} reached without conclusion")
        trace.done(f"investigation hit MAX_STEPS={max_steps}, escalating")
    return ledger
