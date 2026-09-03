# agent

- `router.py` — **the only file in the codebase that names a provider.** Enforced by
  `tests/test_provider_isolation.py` and by an import-linter contract in CI.
  Each lane maps to exactly one deployment so the model is deterministic; cross-provider
  failover happens through the `-alt` sibling lanes in the fallback chain. LiteLLM
  `simple-shuffle` ignores `order` when a lane has several deployments, which would let the
  planner and the critic land on the same model and silently break the independence of the
  check.
- `budget.py` — tokens and cost per run, split by provider, in NPR, with the
  all-`gpt-5.5` counterfactual.
- `cache.py` — response cache keyed on the message hash.
- `trace.py` — the append-only trace. Written before the loop existed. Failed steps stay in.

The degradation ladder is Azure → Groq → deterministic → last known good. There is no local
model lane: `gpt-oss-20b` needs 13–16 GB and the build machine has 7 GB.

## Scout — national breadth, one Groq call

`scout.py` sweeps all 47 PDGLs plus the 2 live corridors in a single call to
`sanket-scout` (`groq/compound`), given deterministic features per basin
(`analysis/eo/national_sweep.py`: ICIMOD danger rank, area, elevation, and an HMAGLOFDB
recurrence count by country) and asked to assign a tier with a one-sentence driver. The
model decides; the features it decides from are all computed by ordinary Python.

**A real failover, not a hypothetical one.** In testing, `groq/compound`'s large-batch
structured response for all 47 basins did not complete inside the router's timeout — the
`sanket-scout` lane failed over to Azure `DeepSeek-V4-Flash`, which returned a complete,
valid assignment in the same call. This is declared rather than hidden: the trace records
`DEGRADED sanket-scout served by azure/DeepSeek-V4-Flash, not groq/groq/compound`, and the
sweep still produced a correct national picture. A deterministic fallback ranking
(`_fallback_assignments`) exists for the case where *both* providers fail on this lane.

`load_tier()` / `cadence_seconds()` are what `watch/daemon.py` reads to schedule each
corridor's tick — Scout never triggers an investigation directly, it only changes how
often Watcher looks, exactly as the brief specifies.
