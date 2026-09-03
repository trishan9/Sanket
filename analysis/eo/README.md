# analysis/eo

Earth observation detection and baselines. No custom training, no YOLO — every detector
here is either a published product reader or a classical, explainable method
(MNDWI+Otsu, a fixed radar backscatter threshold).

- `dswx.py` — reads OPERA DSWx-S1 WTR bands. `independence_group: opera_radar_water`.
- `dist.py` — reads OPERA DIST-ALERT-HLS VEG-DIST-STATUS bands, splitting confirmed
  (classes 3/6/7/8) from provisional (1/2/4/5) disturbance.
- `mndwi.py` — **our own, independent water detector**: MNDWI from Sentinel-2 Green/SWIR1,
  cloud-masked by the scene's own SCL band, thresholded with Otsu — but Otsu's search is
  bounded to `[-0.1, 0.5]` around the literature default (MNDWI > 0), not run on the raw
  histogram. A blind global Otsu on this terrain finds the split between snow/rock and
  everything else, not water and everything else, and returns nonsense thresholds around
  -0.6. `independence_group: sanket_optical` — its entire value is that it shares no
  processing chain with OPERA.
- `radar.py` — a simple fixed-threshold water detector on Sentinel-1 RTC backscatter.
  Declared coarse: a global threshold in steep terrain also catches radar shadow and
  layover, which is why the brief lists this as a known limitation rather than something
  to solve perfectly here.
- `baselines.py` — rolling 14-observation mean and variance per product per tile,
  persisted to SQLite (`core/state.py`, table `baselines`). "Abnormal" is measured from
  real history, never hardcoded.
- `changedetect.py` — z-score classification against a baseline: `within_band`,
  `escalation`, `de_escalation`, using the escalation/de-escalation hysteresis already
  configured in `core/config.py`.
- `lake_series.py` — a per-point lake area time series from MNDWI, with per-observation
  cloud-obscuration flagging and a cloud-gap log (consecutive-clear-observation gaps
  ≥ 20 days).
- `agreement.py` — reprojects and stacks water masks from multiple independent detectors
  onto a common grid and counts per-pixel concordance, feeding both the Verifier's
  independence check and the board's confidence colouring.

## Two real findings from testing against actual data

**A blind Otsu threshold is wrong in this terrain.** The corridor's MNDWI histogram is
unimodal and skewed by snow, ice and rock — not the clean bimodal water/non-water split
Otsu assumes. An unconstrained fit returned thresholds around -0.6 and "detected" up to a
third of the entire scene as water. Bounding the search to a physically plausible range
around the literature MNDWI water threshold (0.0) fixed it; area estimates dropped from
hundreds of km² to sub-2 km², consistent with real mountain lake sizes.

**OPERA DSWx-S1's radar water classification is unreliable over tile T45RUM.** That tile
extends north into high-elevation glaciated terrain (up to 28.93°N, above 5000 m in
places), and its baseline water area comes out at 176 km² — a physically implausible
fraction of the tile. T45RUL, which covers the settlements and the barrier lake site,
gives a sane 5.6 km² baseline. This is read as SAR misclassifying wet snow and glacier
surfaces as open water, a known limitation of radar water products in snow terrain, not a
bug in this reader. **`basin_tiers` and any consumer of the T45RUM baseline should treat
it as low-confidence** until a snow mask is applied — a real, dated finding for the
"cannot_tell_you" list, not a hypothetical one.

## The Purepu result

The exact reported formation-and-drainage week (July 2023) is **98–99% cloud-obscured**
at this specific site — a directly measured confirmation of Phase 1's finding that July is
usable roughly once in 276 scenes. A real, above-detection-floor water signal is present
from November 2023 onward, peaking in January 2025, consistent with the reported growth
pattern even though the exact weekly cadence ICIMOD's own analysis reports could not be
reconstructed from public Sentinel-2 alone. See `notebooks/06b_purepu_detection.ipynb`.
