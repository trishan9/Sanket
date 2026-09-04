from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import jsonify

from agent.loop import MAX_STEPS
from agent.router import DEPLOYMENT_OF, qualified_name
from agent.tools.schemas import GATED_TOOLS, TOOL_DESCRIPTIONS
from core.config import paths, settings

FULL_CHAIN_KINDS = frozenset({"TRIGGER", "VERIFY", "EXPLAIN", "ACTION"})

AGENT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "key": "scout",
        "name": "Scout",
        "role": "Decide which corridors deserve a close watch",
        "lane": "sanket-scout",
        "fires_when": "Weekly national sweep on a cron tick",
        "inputs": [
            "ICIMOD inventory of 47 potentially dangerous glacial lakes",
            "coarse DIST-ALERT disturbance signal per basin",
            "HMAGLOFDB recurrence counts per country",
        ],
        "outputs": [
            "a watch tier per basin: active 15 min, standing 6 h, survey weekly",
            "a standing exposure ranking across all 47 lakes",
        ],
        "tools": ["precedent", "science_lookup", "susceptibility_at"],
        "autonomy": "Changes how often Watcher looks. It never triggers an investigation itself, "
        "so a mistaken promotion costs a few extra ticks rather than a false alarm.",
        "uses_model": True,
    },
    {
        "key": "watcher",
        "name": "Watcher",
        "role": "Decide whether anything is worth investigating",
        "lane": "sanket-classify",
        "fires_when": "Every scheduled tick and on every new granule",
        "inputs": [
            "new OPERA DSWx-S1 and DIST-ALERT granules for the watched tile",
            "Sentinel-1 RTC backscatter over the barrier window",
            "the rolling 14-observation baseline this system computed itself",
        ],
        "outputs": [
            "a z-score against the baseline and a band: within, escalation, de-escalation",
            "a classification word, then an anomaly fingerprint and a queued job",
        ],
        "tools": ["detect_water_change", "detect_disturbance", "search_granules"],
        "autonomy": "Tier 0 and Tier 1 make zero model calls. Only a signal already outside the "
        "band is passed to a model, and only for a single classification word.",
        "uses_model": True,
    },
    {
        "key": "investigator",
        "name": "Investigator",
        "role": "Work out what happened and what it means downstream",
        "lane": "sanket-plan",
        "fires_when": "Watcher classifies an anomaly as investigate",
        "inputs": [
            "the anomaly fingerprint, watched feature and trigger context",
            "an as-of date that filters every piece of evidence behind a temporal firewall",
        ],
        "outputs": [
            "an evidence ledger of typed claims with provenance refs",
            "a concluded or escalated outcome, never a bare answer",
        ],
        "tools": [
            "lake_area_series",
            "precip_percentile",
            "stage_volume",
            "breach_hydrograph",
            "route_flood",
            "exposure_at",
            "met_context",
            "cascade_from",
        ],
        "autonomy": "An open ReAct loop. It chooses its own tools in its own order up to the step "
        "limit, and nothing about that order is hardcoded. It never computes a number itself.",
        "uses_model": True,
    },
    {
        "key": "verifier",
        "name": "Verifier",
        "role": "Decide whether the conclusions are actually supported",
        "lane": "sanket-critic",
        "fires_when": "The Investigator finishes, on every claim in the ledger",
        "inputs": [
            "each proposed claim with its supporting and contradicting evidence refs",
            "retrieved documents from the events collection under the same date cutoff",
        ],
        "outputs": [
            "four checks per claim: independence, temporal validity, licensing, contradiction",
            "a veto reason where a claim fails, and an overall status",
        ],
        "tools": ["science_lookup"],
        "autonomy": "Holds veto power. A single-source claim contradicted by an independent "
        "document is downgraded to insufficient, and the run publishes no conclusion.",
        "uses_model": True,
    },
    {
        "key": "explainer",
        "name": "Explainer",
        "role": "Make the decision legible before anyone acts on it",
        "lane": "sanket-explain",
        "fires_when": "The Verifier finishes",
        "inputs": [
            "the surviving claims, the verification table and a confidence grade",
            "the precomputed scenario grid for counterfactuals",
        ],
        "outputs": [
            "a deterministic decision score with per-term contributions",
            "counterfactuals, flip points, what would change my mind",
            "a public note in English and Nepali, and resident scripts from slot templates",
        ],
        "tools": [],
        "autonomy": "May not introduce a fact absent from the ledger and may not omit a veto. "
        "The decision function is pure Python; the model only writes one context sentence.",
        "uses_model": True,
    },
    {
        "key": "actor",
        "name": "Actor",
        "role": "Make something change in the world, or stop",
        "lane": "sanket-voice",
        "fires_when": "The Explainer finishes",
        "inputs": [
            "the Explainer decision, the settlement lead times and the corridor authority",
        ],
        "outputs": [
            "at or below WATCH: an autonomous board write with the full evidence pack",
            "above WATCH: a gate request to the named district officer, and nothing else",
            "on approval: WhatsApp with a portrait bilingual card, voice audio and SMS",
        ],
        "tools": ["write_status", "voice_call", "send_sms", "send_whatsapp"],
        "autonomy": "This is the only agent that touches the outside world, and the ceiling is "
        "enforced in code rather than by prompt. Above WATCH it cannot proceed alone.",
        "uses_model": True,
    },
)


def _lane_detail(lane: str) -> dict[str, Any]:
    deployment = DEPLOYMENT_OF.get(lane)
    if deployment is None:
        return {"lane": lane, "model": "deterministic", "provider": "none"}
    return {
        "lane": lane,
        "model": deployment.model,
        "provider": deployment.provider,
        "qualified": qualified_name(lane),
        "tpm": deployment.tpm,
        "rpm": deployment.rpm,
    }


def agents() -> Any:
    enriched = []
    for spec in AGENT_SPECS:
        tools = [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS.get(name, ""),
                "gated": name in GATED_TOOLS,
            }
            for name in spec["tools"]
        ]
        enriched.append({**spec, "tools": tools, "routing": _lane_detail(str(spec["lane"]))})
    return jsonify(
        {
            "agents": enriched,
            "max_steps": MAX_STEPS,
            "tool_count": len(TOOL_DESCRIPTIONS),
            "gated_tools": sorted(GATED_TOOLS),
            "autonomous_ceiling": "WATCH",
            "tick_seconds": {
                "active": settings.tick_seconds_active,
                "standing": settings.tick_seconds_standing,
                "survey": settings.tick_seconds_survey,
            },
        }
    )


def _trace_files() -> list[Path]:
    directory = paths.trace
    if not directory.exists():
        return []
    return sorted(directory.glob("*.jsonl"))


def _read_lines(path: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return lines


def _tool_count(item: dict[str, Any]) -> int:
    value = item.get("tools")
    return value if isinstance(value, int) else 0


def full_chain_runs() -> Any:
    candidates: list[dict[str, Any]] = []
    for path in _trace_files():
        lines = _read_lines(path)
        kinds = {str(line.get("kind")) for line in lines}
        agents_seen = {str(line.get("agent")) for line in lines if line.get("agent")}
        if not FULL_CHAIN_KINDS.issubset(kinds):
            continue
        candidates.append(
            {
                "run_id": path.stem,
                "lines": len(lines),
                "agents": sorted(agents_seen),
                "tools": len([line for line in lines if line.get("kind") == "TOOL"]),
                "started": lines[0].get("ts") if lines else None,
                "replay": any(line.get("replay") for line in lines),
            }
        )
    candidates.sort(key=_tool_count, reverse=True)
    return jsonify({"runs": candidates[:12]})


def chain_trace(run_id: str) -> Any:
    path = paths.trace / f"{run_id}.jsonl"
    if not path.exists():
        return jsonify({"run_id": run_id, "lines": [], "error": "no such trace"}), 404
    lines = _read_lines(path)
    by_agent: dict[str, int] = {}
    for line in lines:
        key = str(line.get("agent") or "system")
        by_agent[key] = by_agent.get(key, 0) + 1
    return jsonify(
        {
            "run_id": run_id,
            "lines": lines,
            "counts_by_agent": by_agent,
            "tool_calls": [
                {
                    "tool": line.get("tool"),
                    "args": line.get("args"),
                    "result": line.get("result"),
                    "ts": line.get("ts"),
                }
                for line in lines
                if line.get("kind") == "TOOL"
            ],
        }
    )
