# SANKET code tour

Every claim in the other docs, pointed at the line that implements it. Open the file, read
the twenty lines around the reference, and you have the whole argument.

Order follows the data: **raster → number → anomaly → agent → claim → verification →
decision → gate → delivery**, with prediction as its own section.

---

## 1. Filtering the raster into a number

### 1.1 Class filtering, OPERA DSWx-S1

**`analysis/eo/dswx.py:14-16`** — the class codes we care about, and the ones that mean nothing.

```python
OPEN_WATER = 1
PARTIAL_WATER = 2
NODATA_VALUES = (250, 251, 252, 253, 254, 255)
```

**`analysis/eo/dswx.py:53-55`** — the actual filter. Two masks, not one.

```python
valid = ~np.isin(raw, NODATA_VALUES)
classes = (OPEN_WATER, PARTIAL_WATER) if include_partial else (OPEN_WATER,)
water = np.isin(raw, classes) & valid
```

> **Point at this and say:** "The valid mask is separate from the water mask. Layover and
> shadow in steep terrain produce no-data. If you treat no-data as dry, your area time series
> drifts with the satellite look angle instead of with the water."

**`analysis/eo/dswx.py:67-68`** — raster becomes a single float. This is the whole reduction.

```python
def water_area_km2(observation: WaterObservation) -> float:
    return float(observation.water_mask.sum() * observation.pixel_area_m2 / 1e6)
```

**`analysis/eo/dswx.py:18, 31-34`** — acquisition time is parsed from the filename by regex,
never from file mtime.

> **Why it matters:** ordering a time series by download order is how you silently corrupt a
> baseline.

### 1.2 Adaptive thresholding, Sentinel-2 MNDWI

**`analysis/eo/mndwi.py:99-101`** — the index, with a guarded denominator.

```python
mndwi = np.where(denominator > 0, (green - swir) / np.where(denominator == 0, 1, denominator), 0.0)
```

**`analysis/eo/mndwi.py:39-43`** — the interesting part is not the index, it is the threshold.

```python
def _water_threshold(mndwi, candidate_mask) -> float:
    candidates = mndwi[candidate_mask & (mndwi > MNDWI_SEARCH_LOW) & (mndwi < MNDWI_SEARCH_HIGH)]
    if candidates.size < MIN_CANDIDATES_FOR_OTSU or np.ptp(candidates) < 1e-6:
        return LITERATURE_WATER_THRESHOLD
    return float(threshold_otsu(candidates))
```

Constants at **`analysis/eo/mndwi.py:18-21`**: search band `-0.1` to `0.5`, minimum 200
candidate pixels, fallback threshold `0.0`.

> **Point at line 40 and say:** "Otsu minimises intra-class variance across whatever you hand
> it. Give it a full Himalayan histogram and it will happily split *snow from rock* instead of
> water from land. Restricting it to the −0.1 to 0.5 band is what makes it find the right
> boundary. And line 41 is the bail-out: a 95 percent cloud scene has no bimodal structure, so
> Otsu on it returns confident nonsense."

**`analysis/eo/mndwi.py:59-75`** — B03 is 10 m, B11 is 20 m, so green is reprojected onto the
SWIR grid with **`Resampling.average`** (line 73), not nearest.

> **Why:** nearest-neighbour downsampling of a reflectance band injects aliasing directly into
> the ratio.

**`analysis/eo/mndwi.py:95-96, 104`** — the SCL cloud mask gates the water mask, so cloud
shadow counts as not-clear.

### 1.3 Refusing to report through cloud

**`analysis/eo/lake_series.py:11-12, 51-56`** — cloud is not interpolated over. It is declared.

```python
LOCAL_WINDOW_PX = 30
CLOUD_GAP_THRESHOLD = 0.5
...
local_clear = observation.clear_mask[row-30:row+30, col-30:col+30]
obscured = bool(local_clear.mean() < CLOUD_GAP_THRESHOLD)
area = 0.0 if obscured else _local_area(observation, row, col, LOCAL_WINDOW_PX)
```

> **Point at line 55 and say:** "Cloud is judged in a 30-pixel box around the lake, not
> scene-wide, because a scene can be 70 percent cloud with a clear lake. And an obscured
> observation stays in the series flagged `obscured=True` rather than being dropped. That is
> why the agent could say '5 clear observations out of 10' instead of presenting a 5-point
> series as if it were complete."

---

## 2. Turning numbers into an anomaly

This is the trigger for the entire system, and it involves no AI at all.

**`core/config.py:42-43`** — the two constants that define "unusual".

```python
baseline_observations: int = 14
escalation_z: float = 3.0
```

**`analysis/eo/baselines.py:33-38`** — the rolling window.

```python
window = values[-settings.baseline_observations:]
mean = float(array.mean())
variance = float(array.var(ddof=1)) if len(array) >= MIN_OBSERVATIONS_FOR_VARIANCE else 0.0
```

**`analysis/eo/baselines.py:27-30`** — the z-score itself.

```python
def z_score(self, observed: float) -> float:
    if self.variance <= 0:
        return 0.0 if observed == self.value else float("inf")
    return (observed - self.value) / float(np.sqrt(self.variance))
```

**`analysis/eo/changedetect.py:24-32`** — the classification.

```python
z = baseline.z_score(observed)
if z >= settings.escalation_z:      classification = "escalation"
elif z <= -settings.escalation_z:   classification = "de_escalation"
else:                               classification = "within_band"
```

> **Point at these four lines and say:** "This is the trigger. Nothing else. A tile is
> anomalous when it is three standard deviations from *its own* recent history — not from a
> neighbour, not from a global constant. `ddof=1` because it is a sample of 14, not a
> population. Line 13's `MIN_OBSERVATIONS_FOR_VARIANCE = 3` plus the `warming_up` flag is what
> stops a brand-new tile screaming on its second observation. And the de-escalation branch is
> how we detect a lake that *drained*."

---

## 3. Independence — the guard against fake corroboration

**`core/provenance.py:136-144`**

```python
def independence_count(refs) -> int:
    groups = set(); ungrouped = 0
    for ref in refs:
        if ref.independence_group is None: ungrouped += 1
        else: groups.add(ref.independence_group)
    return len(groups) + ungrouped
```

Groups are assigned at the tool boundary — see `agent/tools/catalog.py` where DSWx-S1 is
tagged `opera_radar_water` and DIST-ALERT is `opera_optical_disturbance`.

> **Point at line 143 and say:** "Two optical products agreeing is *one* source, because they
> share a sensor, an atmosphere and a cloud mask. Without this, an agent citing four correlated
> products looks like four-way corroboration. This is the single most important guard in the
> system."

---

## 4. The agentic parts

### 4.1 What the model is allowed to be

**`agent/loop.py:83-102`** — the system prompt is mostly a list of prohibitions.

Key lines to read aloud:

> "The tools compute every number; you never compute a number yourself, you only choose which
> function to call, with what arguments, and interpret what comes back."

> "Three gated tools (voice_call, send_sms, send_whatsapp) may be requested but will never be
> executed by you; a human must approve them."

**`agent/loop.py:27`** — `MAX_STEPS = 10`. The hard cap on both cost and context growth.

### 4.2 What actually enters the context window

**`agent/loop.py:105-114`** — the entire goal prompt. Roughly 60 tokens.

```python
f"{corridor.name}, location lon={...}, lat={...}. "
f"Downstream settlements: {', '.join(corridor.settlement_names)}. "
f"Trigger context: {json.dumps(trigger)}."
```

**`agent/loop.py:165`** — what a tool returns *into the conversation*.

```python
return json.dumps({"ref": evidence.ref, "claim_type": evidence.claim_type, **evidence.value})
```

> **Point here and say:** "This is the context economy. The conversation gets a ref and a short
> summary. The full evidence record — provenance, method, as-of filter, acquisition time,
> independence group, uncertainty — stays in the ledger keyed by that ref. That is why 24 tool
> calls across four datasets and a full hydraulic chain costs a few thousand tokens, not
> megabytes. No summarisation step, no sliding window, because `MAX_STEPS = 10` means it cannot
> run long enough to need one."

### 4.3 The refusal, in code

**`agent/loop.py:150-154`**

```python
if name in GATED_TOOLS:
    trace.gate(f"step {step}: requested gated tool {name}, not executed autonomously")
    return json.dumps({"status": "gated", "note": f"{name} requires human approval..."})
```

> **Say:** "The delivery tools are in its schema so it *can* ask. It gets refused every time,
> here, before dispatch. The refusal is a property of the system, not of the prompt."

### 4.4 How it recovers from a failure

**`agent/loop.py:160-162`** — errors are handed back to the model as data, not raised.

```python
except (SanketError, KeyError, ValueError) as exc:
    trace.tool(name, args, f"error: {type(exc).__name__}: {exc}")
    return json.dumps({"status": "error", "note": f"{type(exc).__name__}: {exc}"})
```

> **This is the line behind the best moment in the trace.** `route_flood` at 10.269 Mm³
> returned `RegistryError: no precomputed scenario for v10.3_d60_full`. The model saw that
> string, retried at 10, failed again, then bracketed between 5.0 and 1.0 Mm³ and reported both
> as bounds. Nothing in the prompt describes that strategy. Compare it with a fixed pipeline,
> which either crashes or silently skips routing.

**`agent/loop.py:168-181`** — transient network errors get 3 attempts with exponential jitter,
via tenacity, traced as `RETRY`.

### 4.5 Hallucinated citations are a hard error

**`agent/ledger.py:95-98`**

```python
def _resolve_ref(self, ref: str) -> EvidenceRef:
    evidence = self.evidence_by_ref(ref)
    if evidence is None:
        raise ClaimNotInLedgerError(f"evidence ref {ref} is not in this ledger")
```

> **Say:** "If it invents a citation, `propose_claim` raises. Not a warning, not a lower score.
> The claim does not enter the ledger."

### 4.6 It escalates rather than guessing

**`agent/loop.py:334-345`**

```python
for step in range(1, max_steps + 1):
    try:
        if _run_step(...): return ledger
    except AllProvidersFailedError:
        run_deterministic_investigation(corridor, feature_id, ctx, ledger, trace)
        return ledger
try:
    _ = ledger.outcome
except StepLimitReachedError:
    ledger.escalate(None, f"MAX_STEPS={max_steps} reached without conclusion")
```

Two behaviours in one block:

- **Line 338-339:** if every provider is down *mid-run*, it drops into the deterministic
  investigation and still returns a populated ledger.
- **Line 344-345:** if it burns ten steps without concluding, it **escalates**. It does not
  produce a conclusion it cannot support. In the recorded run, its first claim literally says
  the evidence is insufficient.

**`agent/loop.py:326`** — the same deterministic path is also reachable deliberately, which is
what the "Fast chain, no model" button on `/gate` uses.

---

## 5. Verification — why a claim can be killed

### 5.1 The type lattice

**`core/provenance.py:36-52`** — two tables that decide what evidence may support what claim.

```python
PERMITTED_EVIDENCE = {
    "observation":  {"observation"},
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

**`core/provenance.py:128-133`** — must be a subset of permitted **and** intersect required.

> **Point at `PERMITTED_EVIDENCE["observation"]` and say:** "A claim typed `observation` may
> only cite `observation` evidence. A routing result is typed `scenario`. So a simulation can
> never be laundered into a fact about the world. This is a type system for epistemic status,
> and it is checked twice — at claim time in `agent/ledger.py:71`, and again at verification."

### 5.2 The four checks

| Check | Location | What it catches |
|---|---|---|
| Independence | `agent/verifier.py:60-68` | Correlated sources posing as corroboration |
| Temporal | `agent/verifier.py:71-79` | Evidence from after the run's `as_of` date |
| Licensing | `agent/verifier.py:82-87` | Model output presented as observation |
| Contradiction | `agent/verifier.py:104-137` | Literature that disagrees |

**`agent/verifier.py:233`** — the temporal guard in the aggregate.

```python
and ev.provenance.as_of_filter > ledger.as_of
```

> **Say:** "This is what stops the agent seeing the future in a replay. Two layers actually:
> every tool filters its own inputs by `ctx.as_of`, and then the Verifier independently
> re-checks it, because the first layer is enforced by whoever wrote the tool."

### 5.3 The policy, and its asymmetry

**`agent/verifier.py:159-181`**

```python
if not licensing.passed:                                  veto,  "insufficient"
elif not temporal.passed:                                 veto,  "insufficient"
elif not contradiction.passed and not independence.passed: veto,  "insufficient"
elif not contradiction.passed:                            confidence = "low"
```

> **Point at the last two branches and say:** "A contradiction against a well-corroborated
> claim *downgrades* it to low. The same contradiction against a single-source claim *kills*
> it. Corroboration buys you the right to survive disagreement."

---

## 6. The decision — no AI at all

**`agent/decision.py:13-27`** — the weights and thresholds, all in one place.

```python
W_MAGNITUDE = 0.40;  W_LEAD_TIME = 0.35;  W_EXPOSURE = 0.20;  W_CONFIDENCE = 0.15
CONFIDENCE_SCORE = {"high": 1.0, "medium": 0.5, "low": 0.0, "insufficient": -1.0}
EXPOSURE_REFERENCE = 2000.0
WATCH_THRESHOLD = 0.30
ALERT_THRESHOLD = 0.65
```

**`agent/decision.py:91-101`** — the whole decision function.

```python
def decide(inputs: DecisionInputs) -> Decision:
    if inputs.vetoed:
        return Decision("INSUFFICIENT", 0.0, ())
    contributions = (_magnitude_term(...), _lead_time_term(...),
                     _exposure_term(...), _confidence_term(...))
    score = sum(c.contribution for c in contributions)
    return Decision(_status_for_score(score), score, contributions)
```

Two details worth pointing at:

- **`agent/decision.py:74`** — `math.log1p(count) / math.log1p(2000)`.
  > "Log, because the marginal alarm of the 2000th person is not the marginal alarm of the 20th."
- **`agent/decision.py:18-23`** — `insufficient = -1.0`, a **negative** weight.
  > "Poor evidence actively pulls the score down. It does not merely fail to raise it."

**`agent/decision.py:133-145`** — flip points by bisection, 40 iterations.

> **Say:** "When the board says 'flips at z = 0.48', that is not the LLM explaining itself.
> That is a numerical search over a deterministic function. It is a fact, not a narrative."

---

## 7. The human checkpoint

**`actions/levels.py:35, 102-106`** — the autonomy ceiling is a constant and a comparison.

```python
AUTONOMOUS_RISK_CEILING: RiskLevel = "YELLOW"

def requires_approval(level: str) -> bool:
    resolved = coerce_level(level)
    if resolved == "GREY": return False
    return RISK_ORDER[resolved] > RISK_ORDER[AUTONOMOUS_RISK_CEILING]
```

**`actions/actor.py:46-66`** — the fork. This is the whole autonomy story in twenty lines.

```python
if not requires_approval(status):
    result = board_write_status(...)
    return {"autonomous": True, "board_write": result}
record, outcome = send_gate_request(output, run_id, settlement_lead_times, ...)
return {"autonomous": False, "gate_id": record.gate_id, ...}
```

> **Point at line 46 and say:** "That `if` is the entire safety property. It is enforced in
> code, not asked for in a prompt. There is no path from the agent loop to a phone."

**`actions/gate.py:89-104`** — approval requires the registered contact, and checks expiry.

```python
if sender_contact != approver_contact:
    raise UnauthorisedApproverError(...)
if _is_expired(record, datetime.now(UTC)):
    raise GateNotApprovedError(f"gate {record.gate_id} expired at {record.deadline}")
```

> **Say:** "Wrong contact is a 403 and nothing sends. An unanswered gate expires unsent.
> Silence is never consent."

**`actions/gate.py:138`** — `check_cooldown` is why an approval storm cannot become a message
storm.

---

## 8. Prediction, line by line

`analysis/risk/prediction.py`

### 8.1 The constants

**Lines 11-19**

```python
RECORD_YEARS = 190.0
COMPLETENESS_RANGE = (0.30, 0.80)
MONTE_CARLO_DRAWS = 20000
RANDOM_SEED = 20260904
FORMED_DAM_EVENTUAL_FAILURE = 0.85
FORMED_DAM_MEDIAN_DAYS = 10.0
```

### 8.2 The base rate, and why not Wilson

**`analysis/risk/base_rates.py:88-97`** — events joined to inventory, per dam type, with a
**Poisson** interval.

```python
low, high = poisson_rate_interval(count, total)
```

`wilson_interval` still exists at **line 45** for genuinely binomial quantities.

> **Point at line 97 and say:** "Wilson is a binomial proportion interval, bounded at 1. The
> ice-dammed rate is **1.0147 events per lake**, greater than one, because ice-dammed lakes
> drain repeatedly. Wilson clamps that to 1.0 and destroys the signal. So we use an exact
> Poisson rate interval and state the recurrence caveat."

**`analysis/risk/prediction.py:203-208`** — divide by the 190-year record span to get a
per-lake-year rate.

### 8.3 Case A — no dam yet

**`analysis/risk/prediction.py:262-268`**

```python
years = window_days / 365.25
rates = rng.uniform(low_rate, max(high_rate, low_rate + 1e-12), MONTE_CARLO_DRAWS)
completeness = rng.uniform(*COMPLETENESS_RANGE, MONTE_CARLO_DRAWS)
draws = 1.0 - np.exp(-(rates / completeness) * years)
```

> **Point at the `completeness` line and say:** "An 1850s outburst in an empty valley was never
> written down, so the observed rate is a *floor*. We divide by a factor in 0.30 to 0.80. Watch
> the direction: that raises the rate and **widens the interval**. Uncertainty about the record
> makes us less precise, not more confident. A model that wanted to look good would do the
> opposite."

Note it draws `rates` from the **confidence interval**, not from a point estimate — uncertainty
in the base rate propagates all the way through.

### 8.4 Case B — a dam already exists

**`analysis/risk/prediction.py:237-251`** — the defective exponential, conditioned on survival.

```python
ceiling     = rng.uniform(0.75, 0.92, MONTE_CARLO_DRAWS)
median_days = rng.uniform(5.0, 20.0, MONTE_CARLO_DRAWS)
decay       = np.log(2.0) / median_days

survived       = np.exp(-decay * days_since_formation)
still_standing = 1.0 - ceiling * (1.0 - survived)
fails_by_end   = ceiling * (1.0 - np.exp(-decay * (days_since_formation + window_days)))
fails_already  = ceiling * (1.0 - survived)

forward = np.clip((fails_by_end - fails_already) / np.maximum(still_standing, 1e-9), 0.0, 1.0)
```

> **Point at the last line and say:** "This is the whole idea. `still_standing` in the
> denominator is conditioning on the dam having survived this long. A dam that held for three
> weeks carries materially lower forward probability than one that formed this morning. And
> `ceiling` is *defective*: 15 percent of natural dams never fail, so the survival curve has an
> atom at infinity rather than going to 1."

**`analysis/risk/prediction.py:253-268`** — the selector. Note the `or median_rate <= 0.0`:

```python
if already_formed or median_rate <= 0.0:
    return formed_dam_prior_draws(...), FORMED_DAM_STEPS
```

> **Say:** "This was a real bug we found. A landslide dam is not in a *glacial lake* inventory,
> so the inventory prior collapsed to nearly zero for the exact scenario the system exists to
> handle — a confidently wrong answer. Line 261 is the fix."

### 8.5 The evidence update

**`analysis/risk/prediction.py:194-200`** — bounded odds conversion.

```python
def _odds(probability: float) -> float:
    bounded = min(max(probability, 1e-12), 1 - 1e-12)
    return bounded / (1 - bounded)
```

**`analysis/risk/prediction.py:211-234`** — the reading of each indicator. The important branch:

```python
observed = observations.get(indicator.key)
if observed is None:
    readings.append(IndicatorReading(indicator.key, "not observed", "contributes nothing", 1.0, 0.0))
    continue
ratio = indicator.likelihood_ratio_present if observed else indicator.likelihood_ratio_absent
```

> **Point at the `None` branch and say:** "Unobservable is not the same as absent. Not observed
> gets a ratio of exactly 1.0, contributes exactly 0 in log space, and is returned by name in
> the `unobserved` field so the caller can see what we could not see."

**`analysis/risk/prediction.py:280, 285-287`** — the update, done in log space.

```python
log_lr = sum(reading.log_contribution for reading in readings)
posterior_draws = np.array([_probability(_odds(float(p)) * math.exp(log_lr)) for p in prior_draws])
```

> **Say:** "Odds in, odds out. Log space so six multiplications are six additions and nothing
> underflows. And note it applies to *every draw*, not to a point estimate."

### 8.6 The indicators themselves

**`analysis/risk/prediction.py:79-146`** — each with `likelihood_ratio_present`,
`likelihood_ratio_absent`, `citation` and `rationale`.

The one to show is the first, at **line 83**: `likelihood_ratio_present=42.0`.

Then jump to **line 139-140**, the temperature anomaly: `likelihood_ratio_absent=1.0`.

> **Say:** "Read the *absent* column, that is where the epistemics are. Radar absent is 0.55,
> strong evidence against, because radar sees through cloud — if radar did not see it, it
> probably was not there. Optical disturbance absent is only 0.80, because cloud may simply
> have hidden it. And temperature absent is exactly 1.0, explicitly uninformative. The model
> encodes what each sensor is capable of *not* seeing."

### 8.7 Interval and attribution

**`analysis/risk/prediction.py:284, 289-293, 300-303`**

```python
prior_point = float(np.median(prior_draws))
dominant = max(observed_readings, key=lambda r: abs(r.log_contribution)).key
credible_interval=(float(np.percentile(posterior_draws, 5)),
                   float(np.percentile(posterior_draws, 95)))
```

> **Point at line 284 and say:** "Prior and posterior come from the **same draw set**. An
> earlier version computed them on different bases and reported an evidence lift of 1.005 with
> zero evidence. Small lie, total loss of trust. Now lift is exactly 1.0 when nothing is
> observed."

`dominant_indicator` is just the largest `|log contribution|` — which single piece of evidence
moved the answer most.

---

## 9. The hydraulics, for the one who asks

**`analysis/hydro/stage_volume.py:90-99`** — the flood fill that cannot leak.

```python
labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
target = int(labels[row, col])
component = labels == target
```

> **Say:** "8-connected labelling, keeping only the component containing the blockage cell.
> That is what stops the fill draining into an unrelated basin that happens to sit below the
> same elevation."

**`analysis/hydro/stage_volume.py:151-158`** — flood upward in steps, stop at spill
(`_touches_edge`, line 101), integrate depth × pixel area for volume.

**`analysis/hydro/breach.py:44-53`** — three breach modes, gamma-shaped for full and
progressive.

**`analysis/hydro/route1d.py:52-63`** — the Rusanov flux.

> **Say:** "Rusanov, not Roe or HLLC. It is the most diffusive of the three and that is the
> point: a dam-break wave over an 8 m DEM in a steep canyon produces near-dry states and
> transcritical transitions that make Roe linearisation fail without an entropy fix. Rusanov
> cannot produce negative depths and needs no eigenvector decomposition. Its extra numerical
> diffusion is small next to the DEM error."

**`analysis/hydro/route1d.py:97-98`** — the semi-implicit friction, the line that makes it
stable.

```python
friction = GRAVITY * manning**2 * np.abs(velocity) / hydraulic_radius ** (4.0 / 3.0)
next_discharge[1:-1] /= 1 + dt * friction[1:-1]
```

> **Say:** "Dividing, not subtracting. Explicit Manning friction goes unstable in shallow,
> rough, steep reaches — exactly this domain. Semi-implicit is unconditionally stable and
> cannot flip the sign of the discharge."

**`analysis/hydro/route1d.py:113-115`** — adaptive CFL, recomputed every step, raising rather
than silently producing garbage.

**`analysis/hydro/route1d.py:16-20, 34-38`** — Manning's n varies by reach: 0.10 above 39 km,
0.05 to 72 km, 0.04 below.

> **Say:** "One roughness value for a 100 km river is a fiction. A boulder-choked headwater is
> not a graded lower channel."

---

## 10. Resilience

**`agent/router.py:65-79`** — six lanes, each a `Deployment` with a model, provider, TPM and
RPM.

**`agent/router.py:81-92`** — the per-lane fallback map, crossing providers.

**`agent/router.py:94`** — the ladder.

```python
DEGRADATION_LADDER = ("azure", "groq", "deterministic", "last_known_good")
```

> **Say:** "This file is the only module in the repository allowed to import a provider SDK.
> An import-linter contract and an AST test walk the import graph, so adding `import openai`
> anywhere else fails the build. The ban cannot rot."

Test: `tests/test_provider_isolation.py`.

---

## 11. Escalation thresholds

**`actions/escalation.py:33-36`**

```python
CORROBORATION_MIN_INDICATORS = 2
CORROBORATION_MIN_PROBABILITY = 0.25
VERIFICATION_MIN_PROBABILITY = 0.60
STAND_DOWN_MAX_PROBABILITY = 0.05
```

**`actions/escalation.py:111-146`** — `classify_stage`, evaluated highest-severity-first so a
verified RED cannot be masked by a corroborated ORANGE.

---

## 12. A five-minute route through the repo

If someone says "show me the code", go in this order:

1. **`analysis/eo/dswx.py:53-55, 67-68`** — a raster becomes one float.
2. **`analysis/eo/changedetect.py:24-32`** — that float becomes an anomaly. No AI yet.
3. **`agent/loop.py:83-102`** — the prompt is a list of prohibitions.
4. **`agent/loop.py:160-162`** — errors go back to the model as data; this is the retry story.
5. **`agent/ledger.py:95-98`** — a hallucinated citation raises.
6. **`core/provenance.py:36-52`** — model output cannot become an observation.
7. **`analysis/risk/prediction.py:237-251`** — the prediction, conditioned on survival.
8. **`actions/actor.py:46`** — the single `if` that keeps a human in the loop.

Eight files. That is the whole argument.
