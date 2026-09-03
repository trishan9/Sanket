# watch

The autonomy engine. **No human input path exists to start a run.**

- `daemon.py` — process entry. `Daemon.start()` schedules a tick per corridor via
  APScheduler, recovers orphaned runs and queue jobs on startup, then runs unattended.
- `triggers.py` — Tier 0, zero LLM calls. Polls NASA CMR for granules published since
  `last_granule_check` (not from now — a missed tick catches up rather than losing the
  gap), checks DHM river stage (currently always raises, since no public API exists — see
  `core/connectors/dhm.py`), and finds anomalies due for recheck.
- `tiers.py` — Tier 1 (zero LLM: z-score against a rolling 14-observation baseline,
  computed by the system itself, not hardcoded) through Tier 3 (fingerprint, open or
  update an anomaly, enqueue an investigation job). The one LLM call in the whole daemon
  cycle is Tier 2's classification (`investigate | artefact | seasonal |
  insufficient_data`), and it only fires when Tier 1 finds something outside the baseline
  band.
- `queue.py` — the work queue. `enqueue()` / `claim_next()` / `finish()` /
  `recover_orphaned()`. A job claimed but never finished within 30 minutes (a crash mid
  investigation) is returned to `pending` on the next `recover_orphaned()` call, which
  `Daemon.start()` runs automatically.

## Two real bugs found while testing this against a live LLM call

**The "should we recompute the baseline" check was backwards.** It compared
`baseline.n_obs < len(all_history)`, which becomes true forever once more than 14
observations exist — since the rolling baseline is *supposed* to only ever hold 14. That
meant Tier 1 never actually got past "compute and store," and no anomaly was ever
classified. Fixed: recompute only on true cold start (no baseline row exists at all); roll
the baseline forward only when the new observation is itself within-band, so a genuine
ongoing anomaly is never quietly normalised into "the new normal" before Tier 3 sees it.

**A live degradation check was falsely firing on every Groq call.** The router stripped
`"openai/"` from every served-model name to compare it against the intended deployment —
but for Groq's GPT-OSS models, `openai/gpt-oss-20b` **is the real model ID**, not a routing
artefact. Every successful call was misreported as a silent failover. Fixed in
`agent/router.py`, and while there, a second real bug came out of the same fix: Azure
returns dated snapshot names (`gpt-5.5-2026-04-24`), which `agent/budget.py`'s pricing
lookup didn't recognise — every such call was silently costed at **NPR 0.00**. Both fixed
together, since one surfaced the other.

## A known gap, not hidden

`CORRIDOR_TILES` in `tiers.py` maps only `bhotekoshi_trishuli` to a real OPERA tile
(`T45RUL`) — Thame has no EO data fetched yet. `run_tier1()` returns no signal for any
unmapped corridor rather than silently reusing Bhotekoshi's baseline; this was a real bug
caught and fixed, not a hypothetical one.
