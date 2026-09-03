# Vendored from geo-pera/bhotekoshi-2026-reconstruction

Source: https://github.com/geo-pera/bhotekoshi-2026-reconstruction, commit as of
3 September 2026, files under `sim/scripts/`. Licence: MIT (see `LICENSE`).

These files are unmodified except for this README. They are the reference
implementation SANKET's own hydraulics are adapted from — the same numerical
methods (Rusanov-flux 1D Saint-Venant, Audusse-scheme 2D shallow water), the same
citation used to answer "is your simulation real?"

**Why these are not called directly.** They are written as one-off CLI scripts
against a specific 120 km reach (Lhende to Galchhi) with a hardcoded centerline,
a hardcoded post-event DEM this project does not have, and a dependency on
`osgeo.osr` which is not part of this project's stack (`pyproj` is used instead
throughout). `analysis/hydro/route1d.py` and `analysis/hydro/swe2d_torch.py`
reimplement the same numerical schemes against SANKET's own corridor, DEM, and
settlement list, built with the libraries already in this project.

Not credited in the code (per the no-comments rule) — credited here, in the
top-level README's "Brought in" section, and on the board's attribution page.
