from __future__ import annotations

from typing import Any

from agent.tools.context import ToolContext
from core.errors import RegistryError
from core.provenance import Evidence, Provenance


def susceptibility_at(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    from analysis.risk.susceptibility import susceptibility_at as score_for

    score = score_for(args["node_id"])
    if score is None:
        raise RegistryError(f"{args['node_id']} is not in the ranked PDGL inventory")
    return Evidence(
        value={
            "node_id": score.node_id,
            "rank_score": round(score.rank_score, 4),
            "band": score.band,
            "summary": score.rendered(),
            "base_rates": [rate.rendered() for rate in score.base_rates],
            "unobservable_parameters": list(score.unobservable_parameters),
        },
        provenance=Provenance(
            source="ICIMOD PDGL inventory + HMAGLOFDB base rates",
            method="parameter framework ranking, Rounce et al. 2016 and ICIMOD/UNDP 2020",
            as_of_filter=ctx.as_of,
            independence_group="icimod_inventory",
            caveats=score.caveats,
        ),
        claim_type="model_output",
    )


def cascade_from(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    from analysis.risk.cascade_sim import simulate_cascade
    from core.corridor import load_all_corridors

    corridor = load_all_corridors()["bhotekoshi"]
    result = simulate_cascade(corridor, args["node_id"], args.get("breach_volume_mm3", 1.0))
    return Evidence(
        value={
            "origin": result.origin_node_id,
            "summary": result.rendered(),
            "steps": [
                {
                    "order": step.order,
                    "node_id": step.node_id,
                    "node_type": step.node_type,
                    "mechanism": step.mechanism,
                    "confidence": step.confidence,
                }
                for step in result.steps
            ],
            "terminal_confidence": result.terminal_confidence,
        },
        provenance=Provenance(
            source="SANKET cascade graph",
            method="downstream chain walk with per-step confidence decay",
            as_of_filter=ctx.as_of,
            caveats=result.caveats,
        ),
        claim_type="scenario",
    )


def observability_report(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    from analysis.risk.observability import observability_report as build_report

    report = build_report(args["catchment"])
    return Evidence(
        value={
            "catchment": report.catchment,
            "inventoried_lakes": report.inventoried_lakes,
            "below_detection_limit": report.below_detection_limit,
            "below_attention_threshold": report.below_attention_threshold,
            "detection_limit_km2": report.detection_limit_km2,
            "smallest_inventoried_km2": report.smallest_inventoried_km2,
            "summary": report.rendered(),
        },
        provenance=Provenance(
            source="ICIMOD 2015 inventory",
            method="area thresholds against the sensor detection limit",
            as_of_filter=ctx.as_of,
            independence_group="icimod_inventory",
            caveats=report.caveats,
        ),
        claim_type="observation",
    )


def met_context(args: dict[str, Any], ctx: ToolContext) -> Evidence:
    from datetime import date as date_type

    from analysis.met.ruleout import rainfall_explains

    target = date_type.fromisoformat(args["target_date"])
    if target > ctx.as_of:
        raise RegistryError(f"{target} is after as_of={ctx.as_of}; cannot look into the future")
    result = rainfall_explains(target)
    return Evidence(
        value={
            "basin": args["basin"],
            "date": target.isoformat(),
            "rainfall_explains": result.explains,
            "daily_percentile": result.daily_percentile,
            "daily_mm": result.daily_mm,
            "monthly_percentile": result.monthly_percentile,
            "monthly_mm": result.monthly_mm,
            "antecedent_mm": result.anomaly.antecedent_mm,
            "unobserved_layers": list(result.anomaly.unobserved_layers),
            "summary": result.rendered(),
        },
        provenance=Provenance(
            source="CHIRPS v2.0 daily preliminary and monthly",
            method="percentile against same-month climatology, with antecedent accumulation",
            as_of_filter=ctx.as_of,
            independence_group="chirps_precipitation",
            caveats=result.caveats + result.anomaly.notes,
        ),
        claim_type="observation",
    )


RISK_DISPATCH = {
    "susceptibility_at": susceptibility_at,
    "cascade_from": cascade_from,
    "observability_report": observability_report,
    "met_context": met_context,
}
