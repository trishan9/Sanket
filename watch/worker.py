from __future__ import annotations

from actions.pipeline import run_verifier_explainer_actor
from agent.budget import budget
from agent.loop import investigate
from agent.router import gateway
from agent.trace import Trace
from core.corridor import Corridor
from core.state import State
from core.state import state as default_state
from watch.queue import claim_next, finish

WATCHED_FEATURE_ID = "lhende_barrier"


def process_one(corridor: Corridor, store: State | None = None) -> str | None:
    target = store or default_state
    job = claim_next(corridor.basin_id, store=target)
    if job is None:
        return None

    run_id = f"inv_{job.job_id}"
    trace = Trace(run_id, corridor.basin_id, replay=corridor.mode == "replay")
    trace.trigger(f"queued investigation {job.job_id} claimed for {job.payload}")
    target.start_run(run_id, corridor.basin_id, "investigator", "queue", mode=corridor.mode)

    before = len(gateway.degradations)
    anomaly_id = str(job.payload.get("anomaly_id", job.job_id))
    feature_id = str(job.payload.get("feature_id", WATCHED_FEATURE_ID))
    try:
        ledger = investigate(
            corridor, anomaly_id, feature_id, job.payload, run_id, trace, store=target
        )
        trace.done(f"investigation concluded: {ledger.outcome}")
        run_verifier_explainer_actor(corridor, ledger, run_id, trace, target)
        outcome = "concluded" if ledger.outcome.concluded else "escalated"
        finish(job.job_id, "done", store=target)
    except Exception as exc:
        trace.done(f"investigation job {job.job_id} failed: {type(exc).__name__}: {exc}")
        finish(job.job_id, "failed", store=target)
        outcome = "failed"
    finally:
        spent = budget.get(run_id)
        target.finish_run(
            run_id,
            steps=1,
            tokens_azure=spent.tokens_in.get("azure", 0),
            tokens_groq=spent.tokens_in.get("groq", 0),
            cost_npr=spent.total_npr,
            outcome=outcome,
            degradations=gateway.degradations[before:],
        )
    return run_id


def drain(corridor: Corridor, store: State | None = None, *, max_jobs: int = 5) -> list[str]:
    processed: list[str] = []
    for _ in range(max_jobs):
        run_id = process_one(corridor, store)
        if run_id is None:
            break
        processed.append(run_id)
    return processed
