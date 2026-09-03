# analysis/exposure

Turns the Phase 3 scenario grid into what a district officer actually needs: lead time,
isolation risk, and a standing profile per settlement — available before anything happens.

- `cells.py` — exposure counting (population, buildings, bridges, settlement names) inside
  any geometry. `strip_admin_fields()` removes every `adm0-4_*` column before it reaches a
  scoring function, enforcing the rule that admin boundaries are display-only, never
  scoring input — the hazard's source is in another country and does not respect borders.
- `leadtime.py` — looks up arrival time at any settlement for any scenario in the
  precomputed grid; histogram and ECDF helpers.
- `isolation.py` — which bridges near a settlement fall inside a given inundation
  footprint, and whether losing them is a single point of failure.
- `preparedness.py` — the standing profile: lead-time range, exposure, isolation risk,
  DEM vintage, and caveats, computed with **no event and no alert** — this is what the
  board's `/preparedness` route shows on an ordinary Tuesday.
- `assembly.py` — candidate safe-assembly points from OSM open-space polygons, ranked by
  distance and checked against DEM elevation relative to a stated peak-stage value.
- `validation.py` — confusion matrix, IoU, precision and recall against real
  observed-extent products.

## The validation finding — the same story as Phase 3, from an independent source

Validated against two real, independent observed-extent products: **Copernicus EMS
EMSR927** (the official rapid-mapping activation, 50 polygons across 4 AOIs, 19.5 km²) and
**HDX's `hot_flood_npl` flood extent** (27 August 2026, 31.7 km²).

| Reference | Precision | Recall | IoU |
|---|---|---|---|
| CEMS EMSR927 | 0.41 | 0.15–0.19 | 0.12–0.15 |
| HDX flood extent | 0.96–0.97 | 0.19–0.25 | 0.19–0.24 |

**High precision, low recall, at every scenario volume tested.** Nearly everywhere the
model predicts inundation, the official record agrees — but the model captures only a
fifth to a quarter of the true affected area. This is the same finding as Phase 3's
calibration (a −83% depth residual against geo-pera's reconstruction), reached completely
independently: **a water-only shallow-water model systematically under-represents a
mass-movement event.** Two different methods, two different real ground-truth sources,
one consistent, honest conclusion.

**A finding worth carrying forward on its own:** CEMS classifies its observed extent as
`6-Mass Movement / Landslide`, not `flood`. That is Copernicus's own categorisation of the
26 August 2026 event, not a labelling choice made here — independent confirmation that
this was fundamentally a mass-movement event with a water component, not a pure flood.
