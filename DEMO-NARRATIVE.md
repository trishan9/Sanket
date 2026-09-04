# The demo narrative: prediction and detection, fused

The story to tell, page by page, with what to click and what to say. Every number below is
real output, verified against the running system.

The arc in one line:

> **We knew this lake was dangerous before anything happened. Radar noticed the change.
> The prediction updated. The agent investigated. The Verifier checked it. A human signed.
> The village got a map.**

Six beats. Prediction opens it, detection confirms it, and the two multiply.

---

## Say this first, so nothing you say later is oversold

> "This does not predict the date of a disaster. Nothing can. What it does is hold a running
> probability, raise it the moment evidence arrives, say something early and reversibly, and
> harden only when the evidence justifies it."

If you claim it predicted a specific event on a specific day, the first informed question
destroys the demo. Claim the honest thing and the demo survives scrutiny — which is the
stronger position anyway.

---

## Beat 1 — Standing watch

**Page: `/`**

Nothing is happening. That is the point.

> "Eight basins, swept on a schedule. Nobody is logged in and there is no button that starts
> a run. This tier makes zero model calls, so watching the whole country costs nothing."

**5 seconds. Do not linger.**

---

## Beat 2 — Prediction, before anything happens

**Page: `/simulate`, the panel at the top. All indicators on `n/a`.**

The number reads **26.7%**.

> "This is before any evidence at all. This is the base rate: a landslide dam that has already
> formed, and Costa and Schuster's 1988 survey of natural dams — 85 percent eventually fail,
> half of those within ten days — conditioned on how long this one has already held.
> Twenty seven percent in the next seven days, with nothing observed."

**This is your prediction claim, and it is defensible.** You are not predicting an event. You
are saying: *this structure is dangerous, here is the number, before any alarm has fired.*

Point at the credible interval underneath.

> "And it is a range, not a point. Twenty thousand Monte Carlo draws over the failure
> probability and the timing. The range widens where the historical record is thin, which is
> the opposite of what a model tuned to look impressive would do."

**15 seconds.**

---

## Beat 3 — Detection fires

**Page: `/agents`, or stay on `/simulate` and narrate.**

> "Now radar. OPERA DSWx-S1, Sentinel-1, which passes straight through monsoon cloud. Water
> area on the tile against its own last fourteen observations. Three standard deviations out,
> and the cheap tier hands off."

Then the honest bit that makes it credible:

> "The optical scenes for these dates are seventy nine percent cloud. That is exactly why
> detection runs on radar and not on pictures."

**10 seconds.**

---

## Beat 4 — The fusion, and this is the moment

**Back on `/simulate`. Click `yes` on "Radar water anomaly."**

**26.7% → 68.6%.**

> "That is the fusion. The prediction was standing at twenty seven from history alone.
> Detection just supplied one piece of evidence, and it multiplies the odds by six. Sixty
> nine percent."

**Now click `yes` on "Landslide-type seismic event."**

**68.6% → 98.9%.**

> "And a landslide large enough to register seismically. Forty two times, because on this
> river that is how these dams form, and it is instantaneous. Ninety nine percent."

Point at **Strongest evidence**: it reads `seismic_landslide_type`.

> "It tells you which evidence did the work. This is not a black box announcing ninety nine
> percent."

**Then the move that wins the room. Click `no` on "Extreme antecedent rainfall."**

The number barely moves.

> "Watch what happens when I tell it there was no heavy rain. Almost nothing — times
> nought point nine five. Because both real events on this corridor happened on unremarkable
> rainfall days. The model knows that indicator is weak here. And absent radar would have
> been times nought point five five, strong evidence *against*, because radar sees through
> cloud. The model encodes what each sensor is capable of not seeing."

**25 seconds. This is the heart of the demo — do not rush it.**

---

## Beat 5 — The agent investigates, and the Verifier checks it

**Page: `/agents` (or `/trace` for the raw log)**

> "Only now does anything expensive run. The Investigator picks its own tools — twenty four
> calls last run, twelve different tools, in an order nothing hardcodes."

The one detail to show, because it is the most convincing thing in the whole system:

> "The flood router had no precomputed case for ten point two million cubic metres. It failed.
> The agent rounded down to ten, failed again, then bracketed the answer between five and one
> million and reported both as bounds. Nothing in the prompt describes that strategy."

Then verification:

> "Every claim it proposes has to cite evidence refs that exist, or it raises. Then the
> Verifier tries to break each one four ways: are the sources actually independent, does every
> citation resolve before the run's cutoff date, does the evidence type license the claim type,
> and does the literature contradict it."

The line to land:

> "That third check is why a simulation can never become a fact here. A routing result is
> typed `scenario`. A claim typed `observation` may only cite `observation` evidence. It is a
> type system for how much you are allowed to claim."

And the honesty beat:

> "In the run I am showing you, it hit its ten step limit without concluding, so it escalated
> instead of guessing. Its first claim literally says the evidence is insufficient. That is
> the finding, not a failure to produce one."

**20 seconds.**

---

## Beat 6 — The ladder, then the human, then the phone

**Page: `/gate`**

Explain the ladder in one breath, because this answers "why not just one red alert":

| Evidence | Stage | Level | Who releases |
|---|---|---|---|
| One indicator, nothing corroborating | early advisory | **GREY** | autonomous |
| Two indicators, or probability past 25% | corroborated | **ORANGE** | needs a person |
| Verifier passed and probability past 60% | verified | **RED** | needs a person |
| Probability back under 5% | stand down | **GREEN** | autonomous |

> "Confidence arrives gradually, so the alerting does too. GREY says 'something is happening
> and I cannot resolve it yet' — hours before anyone could justify a colour. That is the
> honest failure mode of a cloud-blind system: not a false alarm, silence."

**Now press "Send RED to Timure" and hold the phone up.**

About five seconds later it lands.

> "Real terrain, the real river network, the modelled flood path routed with Saint-Venant,
> in Nepali and English, with the arrival estimate for that specific village. Two minutes at
> Timure."

**Then scroll to the pending gate.**

> "But the agent could not send that. Anything above YELLOW stops here. Here is the score,
> what moved it, and the exact thresholds where the decision flips."

**Press Approve.**

> "One signature, and it goes out in two tiers — institutions first with the evidence, then
> residents with the card. Every send returns a delivery receipt."

Point at the table of Twilio SIDs.

> "Wrong contact is a 403 and nothing sends. An unanswered gate expires unsent after thirty
> minutes. Silence is never consent. But cancelling an alert is automatic, because raising
> fear needs a person and removing it does not."

**20 seconds.**

---

## The whole thing, condensed

If you have 60 seconds, drop beats 1 and 3 and narrate them over beat 2:

1. **`/simulate`** — 26.7% before anything. Base rate, conditioned on survival. *(12s)*
2. **Click radar → 68.6%. Click seismic → 98.9%.** The fusion. *(18s)*
3. **Press "Show the flood map for this."** *(8s)*
4. **`/gate`** — press Send RED, phone buzzes. *(12s)*
5. **Approve, point at the delivery receipts.** *(10s)*

---

## The questions this narrative invites, and the answers

**"So did it actually predict the 26 August event?"**
It would have raised an early GREY advisory when radar first went out of band, and hardened to
RED once the seismic signal and the disturbance confirmed it. What it does not do, and no
system does, is name the day in advance. The value is the lead time between the first advisory
and the wave, not a date.

**"Isn't 26.7% with zero evidence suspiciously high?"**
It is high *because the dam already exists*. That is the survival prior for a natural dam
that has formed, not the rate at which glacial lakes burst. For a moraine lake with no dam,
the base rate is a fraction of a percent. Those are two different questions and the code picks
the right prior for each.

**"How do I know the 99% is not just the AI making something up?"**
No model is involved in that number. It is `analysis/risk/prediction.py`, Bayesian arithmetic
over cited likelihood ratios. You can run it with the network unplugged. The AI's only job in
this system is choosing which measurement to take next.

**"What is the prediction actually for, if it cannot give a date?"**
Three things. It ranks lakes so the watch knows where to look. It sets the escalation stage,
so 25 percent gets ORANGE and 60 percent gets RED. And it makes the alert arguable — a
hydrologist can disagree with a specific likelihood ratio instead of with a black box.

**"What if the prediction is confident and detection sees nothing?"**
Then the absent-indicator ratios pull it down: absent radar is times 0.55. And the escalation
ladder stands down to GREEN autonomously once probability falls under 5 percent. Withdrawing
is as automatic as raising.

**"What if detection fires but the prediction is low?"**
That is GREY, the early advisory. One indicator, nothing corroborating it. It is published,
autonomously, saying exactly that — an anomaly exists and cannot yet be assessed.

---

## The one sentence to close on

> "Prediction tells you which valley to worry about and how much. Detection tells you that
> something just changed. Neither is enough alone — the prediction has no date and the
> detection has no context. Multiplying them is the system."
