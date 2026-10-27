# SANKET, for engineers

Written for someone who will push back. Every algorithm, threshold and constant below is
named with the file it lives in, so you can check the claim against the code.

Companion docs: `EXPLAINER.md` is the non-specialist version, `DEMO.md` is the recording
script.

---

## Part 1 — The signal chain, raster to scalar

The design rule that shapes everything: **no image ever reaches a model.** Every raster is
reduced to a scalar or a short series by deterministic Python before anything else happens.
The model's entire view of the world is JSON.

### 1.1 OPERA DSWx-S1 — the trigger sensor

`analysis/eo/dswx.py`

Sentinel-1 C-band SAR, processed by JPL into a surface-water classification. We read the
`WTR` band, which is a class raster, not reflectance.

```python
OPEN_WATER = 1
PARTIAL_WATER = 2
NODATA_VALUES = (250, 251, 252, 253, 254, 255)

valid = ~np.isin(raw, NODATA_VALUES)
water = np.isin(raw, (OPEN_WATER, PARTIAL_WATER)) & valid
area_km2 = water.sum() * pixel_area_m2 / 1e6
```

Three engineering points worth defending:

- **Partial water is included.** A glacial lake margin and a debris-laden flood are both
  full of mixed pixels. Excluding class 2 would systematically under-read exactly the
  transitional state we care about.
- **The valid mask is separate from the water mask.** Layover and shadow in steep terrain
  produce no-data, and if you treat no-data as dry, an area time series drifts with
  look geometry rather than with water.
- **Acquisition time comes from the filename**, parsed by regex `_(\d{8})T\d{6}Z`, not from
  file mtime. Ordering a time series by mtime is how you accidentally build a baseline out
  of download order.

**Cost of this step: zero model calls.** It is `numpy.isin` and a sum.

### 1.2 The baseline — where "anomaly" is actually defined

`analysis/eo/baselines.py`, `analysis/eo/changedetect.py`

This is the trigger. It is worth being precise because everything expensive downstream
hangs off it.

```python
window = values[-14:]                      # settings.baseline_observations
mean = window.mean()
variance = window.var(ddof=1) if len(window) >= 3 else 0.0
z = (observed - mean) / sqrt(variance)
```

- `z >= 3.0` → escalation
- `z <= -3.0` → de-escalation
- else → within band

Details that matter:

- **`ddof=1`**, sample variance, not population. With n=14 the difference is not academic.
- **Fewer than 3 observations gives variance 0**, and the baseline is flagged
  `warming_up=True`. A zero-variance baseline returns `z = inf` for any change, so
  `warming_up` is the guard that stops a brand-new tile from screaming on its second look.
- **The window is per product, per tile, per statistic**, held in SQLite. A tile is compared
  against its own history, never against a neighbour or a global constant. Steep Himalayan
  terrain has wildly different baseline water areas tile to tile.
- **Symmetry is deliberate.** `z <= -3.0` is de-escalation, and that is how a drained lake
  is detected. A blockage that releases is as diagnostic as one that forms.

**Why a plain z-test and not something fancier?** Because it has to be defensible to a
hydrologist who did not write it, it needs no training data, and it degrades honestly: with
14 samples, a robust estimator or a changepoint model would be fitting noise. The threshold
is a config value (`settings.escalation_z`) precisely so it can be argued with.

### 1.3 Sentinel-2 MNDWI — optical lake area

`analysis/eo/mndwi.py`

```python
MNDWI = (Green - SWIR) / (Green + SWIR)      # B03, B11
```

The interesting part is not the index, it is the thresholding:

```python
candidates = mndwi[clear & (denominator > 0) & (mndwi > -0.1) & (mndwi < 0.5)]
if candidates.size < MIN_CANDIDATES_FOR_OTSU or np.ptp(candidates) < 1e-6:
    return LITERATURE_WATER_THRESHOLD
return threshold_otsu(candidates)
```

- **Otsu is run per scene, not once globally.** Illumination, water turbidity and snow cover
  move the water/land separation between dates. A fixed threshold is why naive MNDWI
  pipelines produce area series that wobble with the sun angle.
- **It is restricted to the −0.1 to 0.5 band.** Otsu minimises intra-class variance across
  whatever you hand it. Give it the full −1 to 1 histogram over a Himalayan scene and it
  will happily split *snow from rock* rather than water from land.
- **It falls back to a literature threshold** when there are too few candidate pixels or the
  histogram is degenerate. A scene that is 95 percent cloud has no bimodal structure to find,
  and Otsu on that returns confident nonsense.
- **B03 is 10 m, B11 is 20 m.** `_resample_to` reprojects green onto the SWIR grid with
  `Resampling.average`, so the ratio is computed on a common grid. Averaging rather than
  nearest, because nearest-neighbour downsampling of a reflectance band injects aliasing
  straight into the index.

### 1.4 The cloud honesty layer

`analysis/eo/lake_series.py`

Cloud is not handled by interpolating over it. It is handled by refusing to report.

```python
LOCAL_WINDOW_PX = 30
CLOUD_GAP_THRESHOLD = 0.5

local_clear = clear_mask[row-30:row+30, col-30:col+30]
obscured = local_clear.mean() < 0.5
area = 0.0 if obscured else _local_area(...)
```

- Cloud is assessed **locally, in a 30-pixel box around the lake**, not scene-wide. A scene
  can be 70 percent cloud and still have a clear lake, and vice versa.
- An obscured observation is **kept in the series with `obscured=True`**, not dropped. This
  is what let the agent say "5 clear observations out of 10, latest clear one from
  2026-01-14" instead of silently presenting a 5-point series as if it were complete.
- SCL classes are used for the clear mask, so cloud shadow counts as not-clear.

### 1.5 Independence groups — the part that stops double counting

`core/provenance.py`

Every `Evidence` record carries an `independence_group`. DSWx-S1 is
`opera_radar_water`; DIST-ALERT is `opera_optical_disturbance`.

```python
def independence_count(refs):
    groups = {r.independence_group for r in refs if r.independence_group}
    ungrouped = sum(1 for r in refs if r.independence_group is None)
    return len(groups) + ungrouped
```

Two optical products agreeing is **one** source, because they share a sensor, an atmosphere
and a cloud mask. This is the single most important guard in the system: without it, an
agent citing four correlated products looks like it has four-way corroboration.

---

## Part 2 — The hydraulic chain

This is the only dataset processed into a chain rather than a scalar, and it is real
numerical hydraulics, not a lookup table.

### 2.1 Stage–volume by barrier-constrained hypsometric fill

`analysis/hydro/stage_volume.py`

The problem: given a DEM and a point where a landslide dammed the river, how much water can
be impounded at each water level?

1. **Find the channel direction.** `descent_vector` looks in a ±6 px window around the
   blockage cell and points at the lowest finite cell. That is the downstream direction.
2. **Build a synthetic barrier** perpendicular to it. `build_barrier` uses a rotated
   coordinate frame — `along` and `across` projections of the pixel index grid onto the
   descent vector — and marks cells within `thickness` along and `half_width` across.
   Cheaper and more robust than rasterising a polygon.
3. **Raise the barrier** to `base + dam_height + step` in a copy of the DEM.
4. **Flood upward in steps.** At each level, take `dammed <= level`, run
   `scipy.ndimage.label` with a 3×3 structure (**8-connected**), and keep only the connected
   component containing the blockage cell. This is what stops the fill from leaking into an
   unrelated basin that happens to sit below the same elevation.
5. **Stop at spill.** If the component touches the window edge, the impoundment is no longer
   contained and the curve is truncated with `spill_limited=True`.
6. **Volume** is `sum(clip(level - elevation, 0, None)) * pixel_area` over the component.

Measured at the Lhende point, 60 m dam: **10.269 Mm³ at spill level 1805.4 m over
344,128 m²**.

The curve carries `void_fraction` and `window_truncated` so a downstream consumer can see
whether the DEM had holes or the window was too small.

### 2.2 Breach hydrographs

`analysis/hydro/breach.py`

Three modes, because "the dam breaks" is not one behaviour:

- **`partial`** — triangular. Peak `2V/T`, rising limb over `T/6`, then linear recession.
  Simple, conservative, mass-exact by construction.
- **`full`** — gamma-shaped, `peak_time = 180 s`, `k = 1.2`. A sharp, near-instantaneous
  collapse.
- **`progressive`** — gamma with `peak_time = 1200 s`, `k = 3.0`. Erosional widening over
  twenty minutes.

The gamma form is `(r·e^(1−r))^k` where `r = t/t_peak`, numerically integrated with
`np.trapezoid` and rescaled so the integral equals the breach volume exactly. `min(r, 50)`
guards the exponential against overflow in the tail.

For 10.269 Mm³ over 60 minutes, full mode: **peak inflow 23,292 m³/s**.

### 2.3 1D Saint-Venant routing with a Rusanov solver

`analysis/hydro/route1d.py`

This is the part most likely to be challenged, so here is the actual scheme.

**Conserved variables:** cross-sectional area `A` and discharge `Q`, on a 1D chainage grid
cut from the DEM.

**Numerical flux — Rusanov (local Lax-Friedrichs):**

```python
wave_speed = |velocity| + celerity           # celerity = sqrt(g * depth)
local_max   = maximum(wave_speed[:-1], wave_speed[1:])
mass_flux     = 0.5*(Q[:-1] + Q[1:])       - 0.5*local_max*(A[1:] - A[:-1])
momentum_flux = 0.5*(QV[:-1] + QV[1:])     - 0.5*local_max*(Q[1:] - Q[:-1])
```

**Why Rusanov and not Roe or HLLC?** Rusanov is the most diffusive of the three and that is
the point. A dam-break wave over an 8 m DEM in a steep canyon produces near-dry states and
transcritical transitions that make Roe linearisation fail without an entropy fix. Rusanov
cannot produce negative depths, needs no eigenvector decomposition, and its extra numerical
diffusion is small relative to the DEM error. It is the boring, robust choice.

**Timestep — adaptive CFL:**

```python
dt = min(0.3 * dx / max(|v| + c), 2.0)      # CFL_NUMBER = 0.3, MAX_DT_S = 2.0
```

Recomputed every step from the current wave speed, and it raises `RoutingError` rather than
silently producing garbage if `dt` collapses to zero or non-finite.

**Source terms, operator-split after the flux update:**

- *Pressure*, a central difference on the water surface `thalweg + stage`:
  `Q -= dt * g * A * dS/dx`
- *Friction*, **semi-implicit**, which is the important bit:
  ```python
  friction = g * n² * |v| / R^(4/3)
  Q /= (1 + dt * friction)
  ```
  Explicit Manning friction goes unstable in shallow, rough, steep reaches — exactly this
  domain. Dividing rather than subtracting is unconditionally stable and cannot flip the
  sign of the discharge.

**Roughness varies by reach**, because one Manning's n for a 100 km river is a fiction:

| Reach | Manning's n |
|---|---|
| 0 to 39 km | **0.10** (boulder-choked headwater) |
| 39 to 72 km | **0.05** |
| below 72 km | **0.04** (graded lower channel) |

**Geometry lookups** are interpolated from per-section stage–area and stage–width tables cut
from the DEM, so channel shape is real terrain rather than an assumed trapezoid.

**Guards:** `MIN_WIDTH_M = 5.0`, hydraulic radius floored at 0.05, velocity clipped to ±60,
area floored at `MIN_AREA_M2`. Every one exists because a real run hit that failure.

**Inflow injection** is spread across three cells (`inject_index ± 1`) rather than a single
point, which prevents a one-cell spike from dominating the local CFL and collapsing `dt`.

### 2.4 Honest calibration

The routed extent is compared against the observed flood extent and reports a **−83 percent
residual**: the model under-predicts. That number is on the validation panel with a stated
reason rather than tuned away. A model calibrated until the chart looked good would be worth
less, not more.

---

## Part 3 — Prediction, in full

`analysis/risk/prediction.py`. Method name in code: *Bayesian indicator update on an
empirical base rate*.

### 3.1 The base rate

`analysis/risk/base_rates.py`

HMAGLOFDB events joined against the ICIMOD 2015 inventory, grouped by dam type, divided by
`RECORD_YEARS = 190.0` to give a per-lake-per-year Poisson rate.

**Why a Poisson interval and not Wilson?** Wilson is a binomial proportion interval, bounded
at 1. The ice-dammed rate is **1.0147 events per lake** — greater than one — because ice-dammed
lakes drain repeatedly. Wilson clamps that to 1.0 and silently destroys the signal. We use an
exact Poisson rate interval with a stated recurrence caveat. `wilson_interval` is still in the
file for genuinely binomial quantities.

### 3.2 Case A — no dam has formed yet

```python
years    = window_days / 365.25
rates    = rng.uniform(low_rate, high_rate, 20000)      # Poisson CI, not a point estimate
complete = rng.uniform(0.30, 0.80, 20000)               # COMPLETENESS_RANGE
prior    = 1 - exp(-(rates / complete) * years)
```

**The completeness factor is the honest part.** The documentary record is demonstrably
incomplete — a 19th-century outburst in an empty valley was never written down. So the
observed rate is a *lower bound*. Dividing by a factor in 0.30–0.80 raises the rate and
**widens the interval**. Note the direction: uncertainty about the record makes the answer
less precise, not more alarming-and-confident.

### 3.3 Case B — a dam already exists

This was a genuine modelling bug we found and fixed, and it is worth telling that way.

The inventory prior is for *glacial lakes*. A landslide-dammed lake is not in a glacial lake
inventory, so for the actual Bhotekoshi case the prior collapsed to nearly zero — a
confidently wrong answer for the exact scenario the system exists to handle.

The fix, from **Costa & Schuster 1988, GSA Bulletin 100:1054**: about 85 percent of natural
dams eventually fail, roughly half of those within 10 days. Modelled as a **defective
exponential** — a survival distribution with an atom at infinity, since 15 percent never fail:

```python
ceiling     = rng.uniform(0.75, 0.92, 20000)     # eventual failure probability
median_days = rng.uniform(5.0, 20.0, 20000)
decay       = ln(2) / median_days

survived       = exp(-decay * days_since_formation)
still_standing = 1 - ceiling * (1 - survived)
fails_by_end   = ceiling * (1 - exp(-decay * (days_since_formation + window_days)))
fails_already  = ceiling * (1 - survived)

forward = (fails_by_end - fails_already) / still_standing
```

That last line is the whole point: **conditioning on survival so far.** A dam that has held
for three weeks carries materially lower forward probability than one that formed this
morning. The `still_standing` denominator is the renormalisation — `np.maximum(x, 1e-9)`
guards the divide.

### 3.4 The evidence update

Odds-form Bayes, in log space:

```python
log_lr    = sum(log(LR_i) for each observed indicator)
posterior = probability(odds(prior) * exp(log_lr))
```

`_odds` bounds the probability to `[1e-12, 1-1e-12]` first, so a prior of 0 or 1 cannot
produce an infinity.

The six indicators — `likelihood_ratio_present` / `likelihood_ratio_absent`:

| Indicator | Present | Absent | Citation |
|---|---|---|---|
| Landslide-type seismic event in basin | **42.0** | 0.85 | USGS ANSS; Costa & Schuster 1988 |
| Confirmed disturbance upstream | **8.5** | 0.80 | OPERA DIST-ALERT; Gruber & Haeberli 2007 |
| Radar water anomaly vs baseline | **6.0** | 0.55 | OPERA DSWx-S1 vs our 14-obs baseline |
| Sustained lake-area growth | **3.2** | 0.70 | Shugar et al. 2020; Rounce et al. 2016 |
| Extreme antecedent rainfall | **2.1** | 0.95 | CHIRPS vs 21-year climatology |
| Positive temperature anomaly | **1.6** | **1.0** | Thame 2024 reconstruction |

Read the **absent** column, it is where the epistemics live:

- **Radar absent = 0.55.** Strong negative evidence, because radar sees through cloud. If
  radar did not see it, it probably was not there.
- **Optical disturbance absent = 0.80.** Weak, because cloud may simply have hidden it.
- **Rainfall absent = 0.95.** Almost nothing, because both events on this corridor happened
  on unremarkable rainfall days. The indicator is retained but honestly discounted.
- **Temperature absent = 1.0.** Explicitly uninformative. A conditioning factor, not a
  trigger.

**An indicator that could not be observed contributes exactly 1.0** and is returned by name
in `unobserved`. Unobservable is not the same as absent, and the API says which is which.

### 3.5 Interval and attribution

- **20,000 Monte Carlo draws**, `RANDOM_SEED = 20260904`, so the number is reproducible.
- Report **median and the 5th/95th percentiles**, a 90 percent credible interval.
- **Prior and posterior come from the same draw set**, so `lift = posterior/prior` is exactly
  1.0 with no evidence. An earlier version computed them on different bases and produced a
  lift of 1.005 with zero evidence, which is the kind of small lie that destroys trust.
- `dominant_indicator` is the observed reading with the largest `|log_contribution|` — which
  single piece of evidence moved the answer most.

### 3.6 Root cause attribution

`analysis/risk/rootcause.py` scores candidate nodes, computes a per-node evidence split, and
reports the **margin between the top two** with `TIE_MARGIN = 0.12`. Below that margin it
declines to name a single cause. An earlier version fed the same observation set to every
candidate node, producing byte-identical evidence for all of them — authoritative-looking and
meaningless. It now scopes observations per node.

---

## Part 4 — What is actually fed to the model

This is the question engineers ask that the marketing deck never answers.

### 4.1 The complete context

The Investigator's context window contains exactly four things:

1. **A system prompt** (~250 words), which is a list of prohibitions more than instructions.
2. **A goal prompt**: the feature id, corridor name, lon/lat, the downstream settlement
   names, and the trigger context as JSON. That is roughly 60 tokens.
3. **Tool schemas** — 16 tools plus 3 gated plus 3 control functions, as OpenAI-style
   function definitions.
4. **The running transcript** of its own tool calls and their returns.

Nothing else. No RAG dump into context, no retrieved documents, no raster, no base64 image.

### 4.2 What a tool return looks like in context

This is the key design decision for context economy:

```json
{"ref": "ev_7faab9b701e5", "claim_type": "scenario", "settlements_reached": 5,
 "fastest_arrival_minutes": 2.0, "max_peak_stage_rise_m": 17.73}
```

The **full** evidence record — provenance, method string, `as_of` filter, acquisition
timestamp, independence group, uncertainty block, and every intermediate array — stays in the
ledger, keyed by that ref. Only the summary enters the conversation.

So a run with **24 tool calls across four datasets and a full hydraulic chain** costs a few
thousand tokens of transcript, not megabytes. The measured total across *all* traced runs is
**23,176 in / 15,363 out over 27 model calls**. Most expensive single run: **NPR 0.73**,
about half a US cent.

Context growth is hard-capped by `MAX_STEPS = 10`. There is no summarisation step and no
sliding window, because the loop cannot run long enough to need one.

### 4.3 How the model talks back

It cannot write prose into the record. It has exactly three control functions:

- `propose_claim(statement, claim_type, supporting_refs, contradicting_refs)` — and
  `ledger.propose_claim` raises `ClaimNotInLedgerError` if a cited ref does not exist. **A
  hallucinated citation is a hard error, not a soft warning.**
- `conclude(summary)`
- `escalate(reason)`

### 4.4 Failure handling inside the loop

- **Tool errors** are caught and returned to the model as
  `{"status": "error", "note": "RegistryError: ..."}`. The model sees the failure and can
  react. This is what produced the observed recovery: `route_flood` at 10.269 Mm³ failed, it
  retried at 10, failed, then bracketed between 5.0 and 1.0 and reported both as bounds.
  Nothing in the prompt describes that strategy.
- **Transient errors** (`ConnectionError`, `TimeoutError`, `OSError`) get 3 attempts with
  `wait_exponential_jitter(initial=1, max=8)` via tenacity, traced as `RETRY`.
- **Gated tools** return `{"status": "gated"}` and emit a `GATE` trace line. The model may ask
  as often as it likes and is refused every time.
- **`AllProvidersFailedError`** drops the whole investigation into
  `run_deterministic_investigation`, mid-run, and still returns a populated ledger.

---

## Part 5 — Why AI at all, when statistics would do

The honest answer is that **statistics does do most of it**, and the AI is confined to the
one job statistics is bad at.

### 5.1 What is not AI

| Function | Method | Model calls |
|---|---|---|
| National basin sweep | Tier scoring on inventory attributes | **0** |
| Anomaly detection | Rolling z-test, n=14, threshold 3σ | **0** |
| Water area | Class masking, pixel count | **0** |
| Lake area | MNDWI + Otsu | **0** |
| Impoundment volume | Hypsometric fill on a DEM | **0** |
| Flood routing | Saint-Venant, Rusanov flux | **0** |
| Lead time | Wave arrival at chainage | **0** |
| Exposure | Spatial join against WorldPop and OSM | **0** |
| Hazard probability | Bayesian update, 20k Monte Carlo | **0** |
| Damage estimate | Depth-damage curves | **0** |
| Alert level | `decide()`, a weighted sum | **0** |
| Approval routing | `requires_approval()`, a comparison | **0** |

**The decision function is pure Python** (`agent/decision.py`):

```python
score = 0.40 * clamp(z / 3.0)
      + 0.35 * clamp(1 - lead_minutes / threshold)
      + 0.20 * clamp(log1p(exposure) / log1p(2000))
      + 0.15 * CONFIDENCE_SCORE[confidence]

ALERT if score >= 0.65, WATCH if >= 0.30, else NORMAL
```

`log1p` on exposure because the marginal alarm of the 2000th person is not the marginal alarm
of the 20th. Confidence can be **negative** (`insufficient = -1.0`), so poor evidence actively
pulls the score down rather than merely failing to raise it.

Flip points are found by **bisection**: `_search_flip` runs 40 iterations to find the exact
value of each input at which the status changes. That is not an LLM explaining itself, it is
a numerical search over a deterministic function. It is why "flips at z = 0.48" is a fact
rather than a narrative.

### 5.2 So what is the AI actually for

Exactly one thing: **choosing which measurement to take next, given what the previous ones
returned.**

That is a sequential experimental-design problem over a heterogeneous tool space, under a
step budget, where the right next action depends on the semantic content of the last result.
Consider the observed run:

1. Optical lake series comes back with 5 of 10 clear and the latest clear observation from
   January. **A fixed pipeline records that and continues.** The agent recognised the series
   could not support a conclusion, and went looking for radar and tile-scale evidence instead.
2. `route_flood` returned `RegistryError: no precomputed scenario for v10.3_d60_full`. A fixed
   pipeline either crashes or silently skips routing. The agent **rounded to 10, failed again,
   then bracketed between 5.0 and 1.0** and framed the result as bounds.
3. It walked `exposure_at` down the corridor at six coordinates it chose, following the
   settlement list it was given.

To hand-code that you would need a decision tree over the cross product of {which tools
failed} × {what the data said} × {which settlements exist}. That tree is unbounded, and every
new tool multiplies it.

### 5.3 The honest counter-argument

**A rules engine would handle 90 percent of cases and be fully auditable.** True. Which is why
the deterministic rung exists and is a first-class execution path, not a stub: it runs the same
tools in a fixed sequence, produces a full evidence pack, and completes in **36 s** versus
**184 s**. When providers are unreachable that is exactly what runs.

The AI buys the **remaining 10 percent** — the runs where a tool fails in a novel way, or the
data is ambiguous in a way nobody enumerated. In an early-warning system, the tail is the
whole product. But we did not bet the system on it: if the AI vanishes, SANKET degrades to a
rules engine and keeps watching.

### 5.4 Why the prediction is not a neural network

- **Sample size.** HMAGLOFDB has 190 years for all of High Mountain Asia. The Bhotekoshi
  corridor has two events. Any classifier fitted on that is fitting noise.
- **Auditability.** A hydrologist can disagree with `LR = 42.0` for a seismic landslide signal
  and argue for 20. They cannot argue with layer 7 of an MLP.
- **Calibration honesty.** The Monte Carlo interval propagates real uncertainty in the base
  rate and record completeness. A softmax output has no comparable notion of "the record we
  trained on is incomplete."
- **Cold start.** The Bayesian model works on day one for a lake never seen before, from the
  dam-type base rate alone. A learned model needs history that does not exist.

If we had 10,000 labelled events we would fit the likelihood ratios instead of eliciting them,
and the structure would not change. The structure is the contribution; the ratios are
parameters.

---

## Part 6 — Verification, the part that makes the agent trustworthy

`agent/verifier.py`, `core/provenance.py`

### 6.1 The claim-type lattice

Six claim types: `observation`, `correlation`, `model_output`, `scenario`, `hypothesis`,
`recommendation`. Two tables govern what can support what:

```python
PERMITTED_EVIDENCE = {
    "observation":  {"observation"},
    "correlation":  {"observation", "correlation"},
    "model_output": {"observation", "correlation", "model_output"},
    "scenario":     {"observation", "correlation", "model_output", "scenario"},
    ...
}
REQUIRED_EVIDENCE = {
    "observation":  {"observation"},
    "model_output": {"model_output"},
    "scenario":     {"model_output", "scenario"},
    ...
}
```

`licenses_claim` requires evidence types to be a **subset of permitted** *and* to
**intersect required**.

The consequence: **a claim typed `observation` cannot cite a model output.** A routing result
can never be laundered into a fact about the world. This is a type system for epistemic status,
checked at claim time and again at verification time, and it is the mechanism behind "all
routing outputs are scenario claims, never predictions" being a property rather than a promise.

### 6.2 The four checks and the policy

1. **Independence** — count of distinct independence groups.
2. **Temporal** — every cited ref must have `as_of_filter <= ledger.as_of`. This is the
   guard that stops the agent seeing the future in a replay.
3. **Licensing** — the lattice above.
4. **Contradiction** — RAG over the science corpus, guarded so documents about the event
   itself cannot be retrieved to "confirm" it.

Policy (`apply_policy`), in precedence order:

- licensing fails → **veto**, confidence `insufficient`
- temporal fails → **veto**, confidence `insufficient`
- contradiction fails **and** independence fails → **veto** (an independent contradiction
  against a single-source claim)
- contradiction fails alone → confidence drops to `low`, not vetoed

Note the asymmetry: a contradiction against a well-corroborated claim **downgrades** it; a
contradiction against a single-source claim **kills** it.

### 6.3 Router and provider isolation

`agent/router.py` is the only module in the repository permitted to import a provider SDK.
Enforced by an import-linter contract **and** an AST test that walks the import graph, so
adding `import openai` anywhere else fails the build.

Six lanes, each with a cross-provider fallback, declared TPM and RPM limits per deployment,
and a degradation ladder `azure → groq → deterministic → last known good`. Verified by
invalidating live API keys at runtime, not by mocking.

---

## Part 7 — Engineer questions, answered

**Why not LangGraph, CrewAI or AutoGen?**
The loop is ~300 lines: a message list, tool dispatch, a step counter, tenacity retry. A
framework adds a dependency, a DSL and a scheduler we would then have to audit. We needed the
control flow to be readable in one sitting because it is the thing that decides whether a
village is warned.

**How do you stop the agent seeing the future in a replay?**
Every tool takes `ctx.as_of` and filters its inputs to `acquired <= as_of`. The Verifier then
independently re-checks that every cited ref resolves within `ledger.as_of`. Two layers,
because the first one is enforced by the tool author and the second is not.

**What if two agents run concurrently on the same basin?**
Runs are keyed by `run_id`; the work queue claims jobs with `claim_next()`; SQLite writes go
through a lock. Gates are per run, and `pending_gate_for_run` takes the most recent pending
row.

**Where is the state?**
SQLite: `runs`, `gates`, `notifications`, `baselines`, `statuses`, `work_queue`,
`heartbeats`, `basin_tiers`, `anomalies`, `granule_checks`. Traces are append-only JSONL per
run. No ORM.

**How do you know the numbers on the board are not stale?**
`heartbeats` plus `written_at` on every status. The degraded fallback page renders last known
good **with its age in hours** rather than hiding it.

**What is the actual latency budget?**
Detection to gate request: **184 s** measured, of which nearly all is the Investigator's model
calls (24 tool calls, ~10 s of compute total). Deterministic path: **36 s**. Card render plus
WhatsApp: **6 s**. Against a fastest modelled arrival of **2 minutes** at Timure — which is why
Tier 0/1 detection has to be model-free, and why GREY exists to say something before the
expensive path finishes.

**Why 900 m corridor cells?**
`CELL_SIZE_M = 900.0`, aggregating the routed raster by max. Small enough to distinguish
settlements, large enough that WorldPop's 100 m grid contributes ~81 cells per aggregate so the
population number is not dominated by a single modelled pixel. Aggregation is by **max, not
mean**, because for hazard the deepest point in a cell is the operationally relevant one.

**Is the priority score a casualty estimate?**
No, and the API returns that sentence in its caveats. It is
`damage_fraction * population + 12 * damaged_buildings + damage_fraction * (6 * helipad_km +
8 * bridges_out)`. A relative triage ordering between cells. The weights are judgement, stated
as judgement.

**What breaks first at scale?**
The scenario grid. It is precomputed over breach volume × duration, and any request outside
that grid returns `RegistryError` — which is exactly what the agent hit at 10.269 Mm³. Honest
failure, but at national scale it becomes a coverage problem rather than an edge case, and the
fix is on-demand routing rather than a denser grid.

**What would you do differently?**
Put river-stage sensors in the corridor. Every arrival time in this system is modelled and
uncalibrated against a real hydrograph. Six gauges would convert the largest source of
uncertainty from an assumption into a measurement, and would let the completeness factor in
the Bayesian prior shrink rather than remain a 0.30–0.80 guess.
