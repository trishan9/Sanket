# How SANKET predicts, and how to demo it live

A version you can hold in your head. The deep version is Part 3 of `TECHNICAL.md`.

---

## The one-liner

> **We start with how often these dams break historically, then multiply that by how
> suspicious today looks.**

That is Bayes' rule in odds form, and it is the whole model.

---

## The four-step story

Remember it as **Base rate → Evidence → Answer → Honesty.**

### Step 1. Base rate — "how often does this happen anyway?"

Two different questions, so two different priors.

**If no dam exists yet** — how often does a lake of this type burst?
From HMAGLOFDB, 190 years of records joined to the ICIMOD lake inventory:

| Dam type | Events per lake |
|---|---|
| Ice-dammed | 1.0147 |
| Moraine-dammed | 0.1948 |
| Bedrock-dammed | 0.0048 |

**If a dam already exists** — this is the Bhotekoshi case, and it is a completely different
question. You are not asking whether a dam will appear. One is standing there. You are asking
whether it will hold.

From **Costa & Schuster 1988**, a survey of natural dams:
- about **85%** eventually fail
- about **half of those within 10 days**

And the crucial move: **condition on how long it has already held.** A dam that survived three
weeks is meaningfully safer than one that formed this morning. Same physics, less risk left.

> *Say it like this:* "A landslide dam is not in a glacial lake inventory, so the inventory
> prior is the wrong prior. We use the survival curve for natural dams instead, and we
> condition on survival so far."

### Step 2. Evidence — "how suspicious is today?"

Six indicators. Each one multiplies the **odds**, not the probability. Each has a number for
present and a number for absent.

| Indicator | If yes | If no |
|---|---|---|
| Landslide-type seismic event | **×42** | ×0.85 |
| Confirmed disturbance upstream | **×8.5** | ×0.80 |
| Radar water anomaly | **×6** | ×0.55 |
| Sustained lake-area growth | **×3.2** | ×0.70 |
| Extreme antecedent rainfall | **×2.1** | ×0.95 |
| Positive temperature anomaly | **×1.6** | ×1.00 |

**The three things to remember about this table:**

1. **Seismic dominates at ×42.** A mountain moving is how these dams form here, and it is
   instantaneous. Nothing else is close.
2. **The "if no" column is the clever part.** Radar absent is ×0.55 — strong evidence *against*,
   because radar sees through cloud, so if radar did not see it, it probably was not there.
   Optical disturbance absent is only ×0.80, because cloud may simply have hidden it.
   **The model knows what each sensor is capable of not seeing.**
3. **Not observed is ×1.0 exactly**, and we list which ones by name. Unobservable is not the
   same as absent.

### Step 3. The answer — odds in, odds out

```
posterior odds = prior odds × ×42 × ×6 × ×0.80 × ...
```

That is it. Multiply the odds, convert back to a probability.

> *Say it like this:* "Everything is multiplication on odds. That is why I can tell you exactly
> which piece of evidence moved the number and by how much."

### Step 4. Honesty — the interval

Two deliberate admissions baked into the maths:

- **The historical record is incomplete.** An 1850s outburst in an empty valley was never
  written down, so the observed rate is a *floor*. We divide by a completeness factor drawn
  from **0.30 to 0.80**. Note what that does: it raises the rate and **widens the interval**.
  Uncertainty about the record makes us *less* precise, not more confident.
- **20,000 Monte Carlo draws** over the uncertain parameters, reported as a median and a
  **90% credible interval**.

> *Say it like this:* "We don't report a single number. We report a range, and the range gets
> wider where the data is thin, which is the opposite of what a model that wanted to look
> good would do."

---

## The numbers to memorise

Real output from `/api/predict/lhende_barrier`, 7-day window:

| Evidence | Probability |
|---|---|
| Nothing observed (pure base rate) | **26.7%** |
| Radar anomaly only | **68.6%** |
| Radar + seismic | **98.9%** |
| Radar + seismic + upstream disturbance | **99.9%** |

**Memorise: 27 → 69 → 99.** That is the demo.

---

## The live demo

**Page: `/simulate`. The panel is at the top: "Turn evidence on and watch the probability
move."**

### Script, about 40 seconds

**Start.** Everything is on `n/a`. The number reads **26.7%**.

> "This is before any evidence. Just the base rate for a dam that has already formed,
> conditioned on how long it has held. Twenty seven percent in seven days."

**Click "yes" on Radar water anomaly.** The number jumps to **68.6%**.

> "Radar sees a step change in water extent against its own fourteen-observation baseline.
> That is a six-times likelihood ratio, and the number goes to sixty nine percent."

**Click "yes" on Landslide-type seismic event.** It jumps to **98.9%**.

> "And now a landslide big enough to register seismically. That is forty two times, because
> on this river that is how these dams form. Ninety nine percent."

**Point at "Strongest evidence".** It reads `seismic_landslide_type`.

> "It tells you which evidence did the work. Not a black box saying ninety nine percent."

**Now click "no" on Extreme antecedent rainfall.** The number barely moves.

> "And watch what happens when I say it was *not* raining. Almost nothing, because both real
> events on this corridor happened on unremarkable rainfall days. The model knows that
> indicator is weak here."

**Press "Show the flood map for this."** In about five seconds the real card appears.

> "And that is the consequence. Real terrain, the real river network, the modelled flood path
> routed with Saint-Venant, in Nepali and English, with the arrival time for that village."

### If you only have 15 seconds

Reset → click **Radar**, click **Seismic** → **27 to 99** → press the flood map button. Say:
"base rate, then evidence multiplies the odds, then the consequence."

---

## Questions you will get, with short answers

**"Is 99% a prediction that it will burst?"**
No. It is the probability of at least one outburst-type event in seven days for a dam of this
class carrying this evidence. Not a date. The API returns that sentence as a caveat on every
response.

**"Where do the likelihood ratios come from?"**
Elicited from the cited literature — Costa & Schuster, Gruber & Haeberli, Shugar et al.,
Rounce et al., USGS ANSS — not fitted. Each one is shown with its citation, so a hydrologist
can disagree with a specific number rather than with the whole model.

**"Why not train a model?"**
190 years of records for all of High Mountain Asia; two events on this corridor. A classifier
on that is fitting noise. Also, someone has to be able to argue with it — you can argue with
×42, you cannot argue with layer 7 of a neural net. If we had 10,000 labelled events we would
fit the ratios and keep the exact same structure.

**"Isn't 26.7% base rate very high?"**
It is high because the dam already exists. That is the Costa & Schuster survival prior, not
the glacial lake inventory rate. For a moraine lake with no dam formed, the base rate is a
fraction of a percent.

**"What if two indicators are really the same signal?"**
That is handled one level up, in the Verifier: evidence carries independence groups, and two
optical products count as one source, not two. The prediction model takes indicators, not raw
sources.

**"Is the flood map computed live when I press the button?"**
The routing is precomputed on a scenario grid; the button renders the card from it — terrain
hillshade, the OSM river network, the depth-coloured flood path and the lead time for that
settlement. Roughly five seconds. And if you ask for a volume outside the grid, it returns an
error rather than extrapolating, which is exactly what the agent hit at 10.269 Mm³.

---

## The one thing not to say

Do not say "the AI predicts". The AI does not predict. **The AI chooses which measurements to
take.** The prediction is Bayesian arithmetic in `analysis/risk/prediction.py` with zero model
calls, and you can run it with the network unplugged.
