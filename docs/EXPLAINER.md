# SANKET, explained end to end

Everything in this file is checkable against the code. Where a number appears, the file
that produces it is named. Where something is synthetic, it says so.

---

## 1. The one paragraph version

A mountainside falls into a river in Rasuwa and dams it. The lake behind that blockage
fills for hours or days, then breaks, and the wave reaches the first village in about
two minutes. Nobody can watch for this by hand: the optical satellites are 79 percent
cloud through the monsoon, the catchment is inside China, and there are no gauges.
SANKET runs a standing watch instead. Twice an hour it pulls fresh radar and rainfall
products, reduces each raster to a single number, and compares that number against a
baseline it computed itself from the previous fourteen observations. That comparison
costs nothing and involves no model. When a number falls outside its own band, an
Investigator agent wakes up, chooses freely from sixteen deterministic Python tools, and
proposes claims that each cite the evidence they rest on. A Verifier tries to break every
claim on four independent grounds. An Explainer turns the survivors into a score with
named contributions and the exact thresholds where the answer would flip. An Actor then
either writes the public board itself, or, if the level is above YELLOW, stops and asks a
named district officer to sign. That is the whole system: cheap arithmetic almost always,
an expensive agent rarely, and a human at the only point where the output reaches the
public.

---

## 2. The datasets, and what actually happens to each one

The important part is not which datasets we used. It is that **nothing downstream ever
sees an image**. Every raster is reduced to a scalar or a short series first, and the
reduction is where the engineering is.

### 2.1 OPERA DSWx-S1 — radar surface water

- **Native form.** A 30 m raster per tile, with a `WTR` band whose pixel values are
  classes: not-water, open water, partial surface water, and several no-data classes.
- **The reduction.** `analysis/eo/dswx.py` keeps the open-water and partial-water classes
  as a boolean mask, then computes `mask.sum() * pixel_area_m2 / 1e6`. A count of pixels
  times the area of one pixel. That is one float: water area in square kilometres.
- **Why it matters most.** Radar is active microwave. It passes through cloud. This is
  the only water measurement that keeps working during the monsoon, which is exactly when
  the hazard peaks.

### 2.2 The baseline, which is where "anomaly" gets defined

`analysis/eo/baselines.py` keeps the last **14** observations per tile per metric, and
computes a rolling mean and variance. `z_score` is then `(observed - mean) / sqrt(variance)`.
`analysis/eo/changedetect.py` classifies:

- `z >= 3.0` → escalation
- `z <= -3.0` → de-escalation
- otherwise → within band

The threshold is `settings.escalation_z = 3.0`. **This is the entire trigger.** No model
is consulted to decide whether something is anomalous. A tile is anomalous when it is
three standard deviations away from its own recent history.

### 2.3 Sentinel-2 L2A — optical lake area

- **Native form.** 10 m multispectral, green and SWIR bands plus a scene classification
  layer.
- **The reduction.** `analysis/eo/mndwi.py` computes the Modified Normalised Difference
  Water Index per pixel: `MNDWI = (Green − SWIR) / (Green + SWIR)`. Water is high, land is
  low. Rather than hardcode a cut, it takes the candidate pixels in the range −0.1 to 0.5
  and runs **Otsu's method** (`skimage.filters.threshold_otsu`) to find the threshold that
  best separates the two modes of that histogram. Pixels above the threshold and marked
  clear become the water mask, then pixels times pixel area gives km² again.
- **The honest bit.** Every observation carries an `obscured` flag. In the series for the
  Lhende point there were **5 clear observations out of 10**, and the most recent clear one
  was from January. The agent said so rather than pretending the series was continuous.

### 2.4 OPERA DIST-ALERT-HLS — surface disturbance

`analysis/eo/dist.py` reads the `VEG-DIST-STATUS` band, keeps only the *confirmed*
disturbance classes, and returns confirmed disturbance area in km². For tile T45RUL on
2026-08-27 that was **53.6634 km²**. This is what a landslide looks like from orbit: not a
picture of a landslide, a number of square kilometres of vegetation that stopped being
vegetation.

### 2.5 CHIRPS — rainfall

`analysis/eo/precip.py` extracts a basin-mean daily rainfall, and
`analysis/met/percentile.py` ranks it against a 21-year same-month climatology. On the
event date the basin mean was **4.23 mm, the 19th percentile**. `analysis/met/ruleout.py`
uses this to *rule out* rainfall as the driver, because the screen requires the 90th
percentile. This is a negative result doing useful work.

### 2.6 HMA 8 m DEM — terrain, and the whole hydraulic chain

This is the one dataset processed into a chain rather than a scalar.

1. `analysis/hydro/conditioning.py` fills sinks so water can route.
2. `analysis/hydro/xsections.py` cuts channel cross sections along the river.
3. `analysis/hydro/stage_volume.py` places a hypothetical barrier of a given height at a
   given point, floods the terrain behind it level by level, and builds a **stage-volume
   curve**: how much water is impounded at each water level. For the Lhende point at 60 m
   dam height this gives **10.269 Mm³ capacity at spill level 1805.4 m over 344,128 m²**.
4. `analysis/hydro/breach.py` turns a breach volume and duration into an inflow
   hydrograph, triangular or gamma-shaped. For 10.269 Mm³ over 60 minutes: **peak inflow
   23,292 m³/s**.
5. `analysis/hydro/route1d.py` routes that wave downstream by solving the **1D
   Saint-Venant shallow water equations** with a **Rusanov flux** finite volume scheme.
   Gravity 9.81, CFL number 0.3, max timestep 2 s, 6-hour run. Manning's roughness varies
   by reach: **0.10** in the upper 39 km, **0.05** to 72 km, **0.04** below that, because a
   boulder-choked headwater is not a graded lower channel.
6. `analysis/exposure/leadtime.py` reads arrival time at each settlement's chainage.

**The DEM is from 2017-07-16.** The barrier formed in 2026. Every claim built on this
chain states that the terrain predates the event. That is not a disclaimer bolted on
afterwards; the Verifier will not let a routing result be typed as an observation.

### 2.7 WorldPop, OSM, HOT — who is actually there

- WorldPop 2020 constrained, 100 m population grid. Modelled usual residence, not a census
  count.
- The HOT activation for this flood: **20 vector layers**, including a computer-vision
  building damage assessment with **1,053 buildings classified** (677 destroyed, 105 major
  damage, 155 minor, 113 no damage), **171 bridges** of which 43 are tagged destroyed, 60
  education facilities, 15 helipads, 10 hydropower sites, and the waterways network.
- `analysis/exposure/corridor_cells.py` aggregates the routed depth raster into **900 m
  cells**, and for each cell counts residents, severely damaged buildings, standing versus
  destroyed bridges within 5 km, distance to the nearest standing helipad, schools, and
  exposed hydropower megawatts.

Measured over the corridor: **79 cells, 11,552 residents, 726 severely damaged buildings
in 15 cells, deepest modelled rise 6.26 m, nearest health facility 26.8 km.**

### 2.8 HMAGLOFDB — the historical record that makes prediction possible

190 years of documented outburst events in High Mountain Asia, joined against the ICIMOD
2015 glacial lake inventory to get events per lake per year by dam type. This is the prior.

---

## 3. How the prediction actually works

This is the part people ask about most, so here it is in full. It lives in
`analysis/risk/prediction.py`. It is **Bayesian updating on an empirical base rate**, not a
neural network, and deliberately so: there is no labelled training set at this sample size,
and a black box would not survive the question "why?".

### 3.1 Case A — no dam has formed yet

**Step 1: the prior.** Take the base rate for this dam type, measured from HMAGLOFDB events
joined to the ICIMOD inventory. Divide by the record span, `RECORD_YEARS = 190.0`, to get a
per-lake-per-year Poisson rate λ.

**Step 2: correct for under-reporting.** A 19th-century outburst in an uninhabited valley
was never written down. So the observed rate is a *lower bound*. Divide λ by a completeness
factor drawn uniformly from **0.30 to 0.80**. This raises the rate and, importantly,
**widens the interval** rather than pretending the record is complete.

**Step 3: convert rate to probability over a window.**

```
P(at least one event in window) = 1 − exp(−λ · years)
```

**Step 4: update on evidence.** Convert prior probability to odds, multiply by a likelihood
ratio for each indicator, convert back:

```
posterior_odds = prior_odds × Π LR_i
```

The six indicators, with the ratio applied when present and when absent:

| Indicator | LR present | LR absent | Source of the ratio |
|---|---|---|---|
| Landslide-type seismic event in basin | **42.0** | 0.85 | USGS ANSS event classification; Costa & Schuster 1988 |
| Confirmed disturbance upstream | **8.5** | 0.80 | OPERA DIST-ALERT; Gruber & Haeberli 2007 |
| Radar water anomaly vs baseline | **6.0** | 0.55 | OPERA DSWx-S1 against our own 14-obs baseline |
| Sustained lake-area growth | **3.2** | 0.70 | Shugar et al. 2020; Rounce et al. 2016 |
| Extreme antecedent rainfall | **2.1** | 0.95 | CHIRPS percentile vs 21-year climatology |
| Positive temperature anomaly | **1.6** | 1.00 | Elicited, weakest indicator |

Three things about this table matter:

- **A seismic landslide signal is worth 42×.** On this river system, mass movement is the
  dominant impoundment mechanism and it is near-instantaneous. Nothing else comes close.
- **The "absent" column is not 1.0 for most rows.** Absence of a radar anomaly is real
  evidence (LR 0.55) because radar sees through cloud. Absence of *optical* disturbance is
  weak evidence (0.80) because cloud may simply have hidden it. The model encodes the
  difference in what each sensor can and cannot see.
- **An indicator that could not be observed contributes exactly 1.0** and is listed by
  name. Unobservable is not the same as absent.

**Step 5: the interval.** Repeat the whole chain over **20,000 Monte Carlo draws** of the
Poisson rate and the completeness factor, seeded at `RANDOM_SEED = 20260904`, and report
the median with a **90 percent credible interval**.

### 3.2 Case B — a dam has already formed

This is the Bhotekoshi case, and the inventory prior is simply wrong for it: you are no
longer asking whether a dam will appear, you are asking whether the one standing there will
break. Landslide dams are not in a *glacial lake* inventory at all, so the naive prior
collapsed to nearly zero for the actual event we were modelling. That was a real bug in an
earlier version.

The fix uses **Costa & Schuster 1988** (GSA Bulletin 100:1054), a survey of natural dams:
about **85 percent eventually fail**, and roughly half of those fail **within 10 days** of
formation. Modelled as a **defective exponential** survival curve: an 0.85 ceiling on
eventual failure, with a 10-day median among those that do fail, and the remaining 15
percent treated as stabilising permanently.

Critically, it then **conditions on survival so far**. A dam that has already held for three
weeks carries a materially lower forward probability than one that formed this morning. Then
the same indicator update and the same Monte Carlo interval as before.

### 3.3 What this is not

It is a probability of at least one outburst-type event in a stated window, for a lake of
this class carrying these indicators. **It is not a prediction of a date.** The likelihood
ratios are elicited from cited literature, not fitted, because no labelled set of this size
exists. The part of the system that *is* validated against observation is the downstream
consequence model, checked against the observed flood extent, and it reports a **−83 percent
residual** with a stated reason rather than a flattering number.

---

## 4. The six agents

| Agent | Wakes when | Input | Output | Model |
|---|---|---|---|---|
| **Scout** | Weekly sweep | 8 basins, lake inventory | A watch tier per basin | none |
| **Watcher** | Every scheduled tick | Latest radar granule | z-score, in or out of band | none |
| **Investigator** | z outside ±3σ | One watched feature | Claims, each citing evidence refs | gpt-5.5 |
| **Verifier** | Claims exist | Proposed claims | Passed or vetoed, with reasons | grok-4.6 |
| **Explainer** | Verification done | Surviving claims | Score, contributions, flip points | gpt-oss-120b |
| **Actor** | Decision exists | A decision | Board write, or a gate request | none |

**Four of the six use no model at all.** That is the cost design: the two that run
constantly are pure arithmetic, so a national sweep every fifteen minutes is free.

### 4.1 The Investigator is the only free-running one

It gets sixteen tools and up to **ten steps** (`MAX_STEPS = 10` in `agent/loop.py`). Nothing
about the order is hardcoded. Its system prompt is explicit about the constraints:

- It may not state that an outburst is likely or imminent, because this imagery cannot
  establish that.
- It may not attribute anything to climate change.
- All routing outputs are scenario claims, never predictions.
- It must report that the DEM predates the event whenever it uses routing.
- **The tools compute every number; it never computes a number itself.** It chooses which
  function to call, with what arguments, and interprets what comes back.

It communicates only through `propose_claim`, citing refs its tool calls returned. If the
evidence is insufficient it calls `escalate` rather than guessing.

**The sixteen tools:** `search_granules`, `detect_water_change`, `detect_disturbance`,
`lake_area_series`, `precip_percentile`, `stage_volume`, `breach_hydrograph`, `route_flood`,
`exposure_at`, `precedent`, `science_lookup`, `write_status`, `susceptibility_at`,
`cascade_from`, `observability_report`, `met_context`.

**Three gated tools exist only to be refused:** `send_whatsapp`, `send_sms`, `voice_call`.
They are in the schema so the refusal is a property of the system rather than of the prompt.

### 4.2 The Verifier has veto power

Every claim is checked four ways (`agent/verifier.py`):

1. **Independence.** How many independent sources support it? Sources carry an
   `independence_group`, so two optical products count as **one** source, not two.
2. **Temporal.** Does every cited piece of evidence resolve within the run's `as_of` date?
   This is what stops the agent from seeing the future in a replay.
3. **Licensing.** Does the *evidence type* license the *claim type*? A `model_output` cannot
   support a claim typed `observation`. This is the mechanism that stops a simulation from
   being laundered into a fact.
4. **Contradiction.** RAG retrieval over the science corpus, guarded so that documents about
   the event itself cannot be retrieved and used to "confirm" it.

A claim that fails is **vetoed**, not softened.

### 4.3 The evidence ledger

Every tool return is stored as an `Evidence` record with a ref like `ev_e7b17dd007fd`, a
provenance block naming the source, the method, the `as_of` filter, the acquisition time,
and an independence group. Claims cite refs. The Verifier resolves refs. Nothing in the
chain is an unsourced assertion.

---

## 5. The alert ladder, and why it is not a single RED

Confidence in this hazard arrives gradually. A system that stays silent until it is certain
is silent exactly when the lead time is most valuable.

| Stage | Level | Meaning | Who releases it |
|---|---|---|---|
| Early advisory | **GREY** | Something is anomalous and cannot yet be assessed | autonomous |
| Watch | **YELLOW** | Real signal, single source | autonomous |
| Corroborated | **ORANGE** | Two independent sources, probability past 0.25 | needs a person |
| Verified | **RED** | Probability past 0.60, claims survived verification | needs a person |
| Stand down | **GREEN** | Probability back under 0.05 | autonomous |

Thresholds live in `actions/escalation.py`: `CORROBORATION_MIN_INDICATORS = 2`,
`CORROBORATION_MIN_PROBABILITY = 0.25`, `VERIFICATION_MIN_PROBABILITY = 0.60`,
`STAND_DOWN_MAX_PROBABILITY = 0.05`.

**Why GREY exists.** The honest failure mode of a cloud-blind system is not a false alarm,
it is silence. GREY lets the system report that it is looking at something it cannot resolve,
hours before it could justify a colour.

**Why GREEN is automatic.** Requiring a signature to *cancel* would leave stale alerts
standing whenever an approver is asleep. Raising fear needs a person. Removing it does not.

---

## 6. The human checkpoint

`AUTONOMOUS_RISK_CEILING = "YELLOW"` in `actions/levels.py`, and `requires_approval()` is a
function, not a prompt instruction.

When the Actor crosses it:

1. A gate opens with a **30 minute** deadline, recording the run id and evidence refs.
2. The approver is notified twice: a WhatsApp message with the exact card that would go out,
   and an entry in the portal queue at `/gate`.
3. Approval requires the **registered approver contact**. Any other contact is refused with
   **403** and nothing is sent.
4. On approval it fans out in two tiers: institutions get the score and evidence summary,
   residents get the portrait card in Nepali and English with their own arrival estimate.
5. Every send returns a Twilio SID stored against the run; the delivery-status webhook
   updates it in place.
6. Rejection closes the gate. **A lapsed 30-minute window does the same.** Silence is never
   consent.

A per-settlement cooldown (40 minutes) means an approval storm cannot become a message storm.

---

## 7. Resilience

The degradation ladder is `azure → groq → deterministic → last known good`.

Six named lanes, each with a fallback across providers:

| Lane | Primary | Fallback | Job |
|---|---|---|---|
| `sanket-plan` | gpt-5.5 | gpt-oss-120b | Investigator |
| `sanket-critic` | grok-4.6 | qwen3.8-27b | Verifier |
| `sanket-explain` | gpt-oss-120b | DeepSeek-V4-Pro | Explainer |
| `sanket-scout` | groq/compound | DeepSeek-V4-Flash | National sweep |
| `sanket-classify` | gpt-oss-20b | DeepSeek-V4-Flash | Cheap triage |
| `sanket-voice` | gpt-audio | — | Spoken Nepali |

**No provider SDK is imported anywhere except `agent/router.py`.** An import-linter contract
and an AST test enforce it, so the ban cannot rot.

The **deterministic rung** runs the same tools in a fixed sequence with no model at all and
still produces a decision with a full evidence pack. Measured: a full adaptive chain takes
**184 s**; the deterministic chain takes **36 s**.

---

## 8. Cost, latency and context

| Measure | Value | Note |
|---|---|---|
| Full agentic chain, trigger to gate | **184 s** | 24 tool calls |
| Deterministic chain | **36 s** | no model calls |
| Drill alert, render plus WhatsApp | **6 s** | real Twilio send |
| Tool calls in one run | **24** | model-chosen, 12 distinct tools |
| Tokens across all traced runs | **23,176 in / 15,363 out** | 27 model calls |
| Most expensive single run | **NPR 0.73** | about USD 0.005 |
| Tier 0 and 1 cost | **zero** | no model is called |

**Context management.** The Investigator's context is the system prompt, a goal prompt, and
the running tool-call transcript. It is bounded by `MAX_STEPS = 10`, which caps context growth
hard. Tool results returned into context are **refs and short summaries**, not raster dumps —
a routing result enters the conversation as `ref=ev_7faab9b701e5 claim_type=scenario`, while
the full numbers stay in the ledger. That is why a run with 24 tool calls over four datasets
still fits comfortably. There is also a response cache keyed on lane plus messages
(`agent/cache.py`), and per-lane TPM and RPM limits declared on each deployment.

---

## 9. Every question we expect, with answers

### On the AI

**Is the model making up the numbers?**
No. The model computes nothing. Sixteen Python functions compute; the model picks which to
call and reads the result. Every number in a claim carries an evidence ref that resolves to
a provenance record. This is enforced by the system prompt *and* by the Verifier's licensing
check.

**Is this just a chatbot with a map?**
No. Nothing starts a run. There is no input path from a user to the investigation loop. The
trigger is a z-score crossing a threshold in a scheduled job.

**Why not train a model to predict outbursts?**
There are not enough labelled events. HMAGLOFDB has 190 years of records for all of High
Mountain Asia; the Bhotekoshi corridor has two. Fitting a classifier on that would produce a
confident-looking number with no support. Bayesian updating on a cited base rate is honest
about how little data exists, and every ratio can be argued with individually.

**What if the LLM hallucinates a claim?**
It gets vetoed. A claim must cite refs that exist in the ledger; `ClaimNotInLedgerError` is
raised if it invents one. Then the licensing check rejects claim types the evidence does not
support, and the independence check downgrades confidence when sources are not independent.

**Why LangGraph / CrewAI / AutoGen isn't used?**
It isn't. The loop is about 300 lines in `agent/loop.py`: a message list, a tool-call
dispatch, a step counter, and a retry policy. A framework would have added a dependency and
hidden the control flow we most needed to audit.

**How many agents really, and are they just prompts?**
Six roles. Four use no model at all — Scout, Watcher and Actor are plain Python, and the
deterministic rung of the Investigator is too. Only the Investigator, Verifier and Explainer
call a model.

### On the data

**Why radar instead of optical?**
The post-event optical scenes are **79 percent cloud**. We show both scenes on `/imagery`
rather than hiding the bad one. Radar is active microwave and passes through cloud, which is
why every trigger path runs on it.

**Your DEM is from 2017 and the event is 2026. Isn't that fatal?**
It is a real limitation and every routing claim states it. The terrain that existed before
the landslide is the correct terrain for asking "if this dam breaks, where does the water
go", because the valley downstream is largely unchanged. It is the *wrong* terrain for the
blockage itself, which is why we never claim to have observed the barrier's geometry.

**Where does the population number come from?**
WorldPop 2020 constrained. It is **modelled usual residence**, not a count, and it cannot
show displacement after an event. Stated in the caveats on every exposure output.

**Is the building damage real?**
Yes, it is the HOT activation's computer-vision assessment over post-event imagery: 1,053
buildings classified, each with its own confidence. It is not a field survey, and we say so.

**The source catchment is in China. How can this work?**
Partly it cannot, and we say that. There are no ground gauges and no guaranteed imagery
sharing. What does work is that OPERA and Sentinel are global and public, so the satellite
path needs nobody's permission. The gap is a diplomatic problem, not a software one.

### On the alerting

**What stops it spamming people?**
Three things. The autonomy ceiling means nothing above YELLOW sends without a signature. A
40-minute per-settlement cooldown suppresses repeats. And the gate expires unsent after 30
minutes rather than defaulting to send.

**What if the approver is asleep?**
Nothing goes out. That is the deliberate choice. The board still updates autonomously up to
YELLOW, so the information is public even when the loud channels are not used.

**Why can it cancel alerts on its own but not raise them?**
Asymmetric cost. A wrong RED evacuates a village for nothing and burns trust. A wrong GREEN
is a return to the normal state. Requiring a human to cancel would strand alerts.

**Is the WhatsApp real?**
Yes, through Twilio, with stored message SIDs and a delivery-status webhook. The approver's
number is real. **The institutional contact numbers are not routable** and are declared
synthetic.

### On honesty

**What is mocked?**
Institutional contacts (non-routable), SMS sending (simulated gateway, no carrier), the
voice call's dial-out (audio synthesis is real, the outbound call is not), and the replay
clock, which compresses elapsed time only — every granule, DEM read and solver output it
drives is real and filtered by an `as_of` date. The precomputed scenario grid is real solver
output but is always typed `scenario`, never `observation`.

**Your flood model has a −83 percent residual. Isn't that bad?**
It is bad, and reporting it is the point. The scenario grid is calibrated against an
independent reconstruction and under-predicts. We show the number and the stated reason
rather than tuning until the chart looked good.

**What can this system not do?**
It cannot predict the trigger. It cannot see a lake that forms and drains between two
satellite passes, which apparently happened at Purepu in July 2023. It cannot count people.
And it cannot decide to evacuate anyone — that belongs to local authority.

### On engineering

**How do you know the provider isolation holds?**
An import-linter contract plus an AST test that walks the import graph. Adding
`import openai` to any module outside `agent/router.py` fails the build.

**What else is enforced by tests?**
Zero comments in source packages, functions under 40 lines, files under 400 lines, full type
hints. 154 tests pass, plus ruff and mypy.

**How did you verify the failover?**
By invalidating live API keys at runtime and watching the ladder degrade through Groq to
deterministic mode, which still produced a decision with a full evidence pack.

**What would you build next?**
Ground truth. A handful of river-stage sensors in the corridor would turn every modelled
arrival time into a validated one, and would let the completeness factor in the Bayesian
prior shrink rather than stay a 0.30-0.80 guess.
