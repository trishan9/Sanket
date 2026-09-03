# analysis

Deterministic computation. **The LLM never computes a number** — every quantity in the
system comes from a function in here.

- `hydro/dem.py` — windowed access to the NASA HMA 8 m DEM. All reads are windowed; the
  full tiles are 12500x12500 float32 and will not fit in memory.
- `hydro/stage_volume.py` — the hypsometric stage–volume curve at a blockage point. A
  landslide dam is modelled explicitly: a barrier of stated crest height is imposed across
  the channel just downstream of the blockage cell, and water is impounded upstream from
  it. Filling naively from a channel cell yields nothing, because the water simply follows
  the channel out of the domain.
- `eo/` — detection and baselines (Phase 4).
- `exposure/` — lead times, isolation, preparedness (Phase 5).

The DEM is from 2017 and predates the 2026 event. Every output carries that caveat.
