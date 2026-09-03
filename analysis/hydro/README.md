# analysis/hydro

Terrain and hydraulics. Every number here is deterministic Python — no LLM computes
a value; an agent (once built) only chooses which of these functions to call.

**The DEM is real, dated 2017-07-16, and every output here carries that vintage.**
Post-event terrain has been reshaped by an enormous debris volume; routing on
pre-event terrain is wrong in ways that cannot be corrected without new survey.

- `dem.py` — windowed access to the NASA HMA 8 m DEM tiles. Never loads a full
  12,500×12,500 tile into memory.
- `stage_volume.py` — hypsometric stage-volume curve at a blockage point. A landslide
  dam is modelled explicitly as a barrier across the channel; filling naively from a
  channel cell returns zero, since water simply follows the open channel out of the
  domain.
- `conditioning.py` — DEM conditioning via `pysheds`: fill depressions, resolve flats,
  D8 flow direction and accumulation, channel extraction. The DEM's own `-9999` void
  cells are filled by nearest-valid-neighbour interpolation *before* conditioning —
  feeding them through unfilled makes pysheds treat a data hole as a literal chasm,
  which breaks flow routing catastrophically. Validated: the extracted channel passes
  within 16–129 m of every real settlement in the corridor.
- `xsections.py` — cross-section hypsometry (stage vs. wetted area and top width) at
  200 m intervals along the traced channel, same algorithm as the vendored geo-pera
  reference (`forked/geopera/xsections.py`), built on our own terrain instead of
  their hardcoded centerline.
- `breach.py` — three parametric breach hydrograph shapes (`partial`, `full`,
  `progressive`), adapted from the vendored reference's hydrograph functions.
- `route1d.py` — 1D Saint-Venant router: Rusanov-flux finite-volume scheme,
  semi-implicit Manning friction, same numerical method as
  `forked/geopera/route1d.py`. Runs a 3-hour simulation over a 62 km, 314-section
  channel in under 10 seconds on CPU.
- `scenarios.py` — precomputes the volume (0.5–5.0 Mm³) × breach duration (5 min–6 h)
  scenario grid, 56 combinations, as compact per-scenario arrays under
  `dist/scenario_grid/`.

**A real bug worth remembering:** the injection boundary originally used
`area[index-1:index+2]` with `index=0`, which silently wraps to a negative-index slice
in NumPy and injects *zero* water. Every "downstream response" observed before the fix
was the initial condition relaxing, not the simulated flood — a reminder that a
numerically stable, non-crashing run is not the same as a correct one.
