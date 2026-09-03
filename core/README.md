# core

The bottom layer. Nothing here imports from any other package.

- `config.py` — settings and paths. All tunables live here, secrets come from `.env`.
- `errors.py` — the typed exception hierarchy. Never raise a bare exception, never catch one.
- `provenance.py` — the evidence envelope. `Evidence` carries a value, a `Provenance` record
  and a `claim_type`. `RENDER_STYLE` maps claim types to visual styles so the renderer can
  refuse to draw a `scenario` like an `observation`. `licenses_claim` enforces that an
  observation does not license a scenario claim.
- `corridor.py` — typed loader for `core/watch/*.yml`. Adding a corridor is a data
  operation: drop in a YAML file, no code changes.
- `state.py` — SQLite persistence for every cross-run memory: basin tiers, baselines,
  anomalies, runs, notifications, gates, subscribers, statuses, the work queue.
  It sits in `core` rather than `watch` because both the daemon and the actions layer
  depend on it, and the layering contract requires shared infrastructure at the bottom.
- `registry/` — one provenance contract per data layer, including `independence_group`
  and `cannot_tell_you`.
- `watch/` — corridor definitions.
