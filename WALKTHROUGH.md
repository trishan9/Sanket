# SANKET: the complete walkthrough

Everything that exists, what it does, whether it is real, and how to show it. Written so you
can walk any visitor through the system without preparation.

---

## Start the system

```bash
# 1. tunnel, so Twilio can fetch the flood map (skip and images will not attach)
~/.local/bin/cloudflared tunnel --url http://127.0.0.1:5000
#    put the https URL into .env as PUBLIC_BASE_URL, then restart the API

# 2. API
.venv/bin/python3 -m flask --app api.app run --port 5000 --no-reload

# 3. board
cd board && npx next dev -p 3000
```

Open `http://127.0.0.1:3000`.

---

## Part 1 — The thirteen pages

### `/` Standing watch
**Shows** live status per settlement on the Bhotekoshi–Trishuli corridor, the corridor level,
and when each was last written.

**Say:** "Nobody is logged in. There is no button that starts a run. Everything here was
written by the system on its own authority, because it is at or below YELLOW."

**Real:** the statuses, the timestamps, the settlement list.

---

### `/simulate` Simulation and live prediction
**The most useful page in a demo.** Two things stacked.

**Top: live prediction.** Six indicators with yes / no / n-a buttons. Toggle and the
probability moves instantly, with the credible interval, the evidence lift and which indicator
dominated.

- Start: **26.7%** (base rate alone)
- Click radar: **68.6%**
- Click seismic: **98.9%**
- Click "no" on rainfall: **98.8%**, barely moves

Then **"Show the flood map for this"** renders the real card in about five seconds.

**Bottom: scenario runner.** Pick a breach volume and duration, run it against the precomputed
scenario grid, the cascade graph, the hazard model and the damage bands at once. Includes a 2D
and 3D terrain toggle on the hazard map.

**Real:** all of it. The routing is precomputed solver output, labelled `scenario`.

---

### `/gate` Approvals, the human checkpoint
**Shows** pending gate requests with the alert card, the decision score, what moved it, and
where the decision flips. Plus three buttons.

| Button | What it does | Time |
|---|---|---|
| **Full chain, agent picks tools** | Real replay, gpt-5.5, 24-ish tool calls | ~184 s |
| **Fast chain, no model** | Same tools, deterministic order, no LLM | ~36 s |
| **Send ORANGE / RED to Timure** | Renders the card and delivers over WhatsApp | ~6 s |

**Say:** "This is the only screen in the system where a public alert is released, and it is
signed by a named contact."

**Real:** the gate, the 403 on a wrong contact, the 30-minute expiry, the Twilio delivery
receipts. Approve, and institutions then residents receive real messages.

---

### `/agents` Agent theatre
**Shows** all six agents with their inputs, outputs, tools, autonomy level and the model each
uses, plus a live trace stepper that replays a real run event by event.

**Say:** "Four of the six use no model at all. Scout, Watcher and Actor are plain Python."

**The detail to point at:** in the trace, `route_flood` fails twice at 10.269 Mm³, then the
agent brackets between 5.0 and 1.0 Mm³. Nothing in the prompt describes that.

---

### `/predict` Prediction detail
**Shows** the hazard model output for each watched node: prior, posterior, credible interval,
every indicator with its likelihood ratio and citation, the method steps, and the caveats.

**Say:** "Every likelihood ratio names its paper. You can disagree with 42 and argue for 20."

---

### `/analysis` Root cause
**Shows** candidate causes ranked, with a per-node evidence split and the margin between the
top two. Below a 0.12 margin it declines to name a single cause.

**Say:** "It will refuse to attribute when the evidence does not separate two candidates."

---

### `/alerts` Alert history and the ladder
**Shows** the five-stage escalation ladder and the alert history with levels, times and which
were autonomous versus gated.

---

### `/imagery` Before and after
**Shows** two real Vantor WorldView scenes swiped against each other, with the modelled
inundation and the ICIMOD lake polygons on top.

**Say this, do not hide it:** "The post-event scene is 79 percent cloud. The two scenes barely
overlap, and the barrier itself sits outside the pre-event scene entirely. That is the monsoon
blindness argument, and it is why detection runs on radar."

**Real, including the flaws:** the black wedges are genuine no-data in the source COGs.

---

### `/preparedness` Exposure and lead time
**Shows** per settlement: population, buildings, bridges, bridges at risk, single point of
failure, minimum and maximum lead time, DEM vintage and caveats.

**The number that lands:** fastest modelled arrival at Timure is **2 minutes**.

---

### `/gov` Technical dashboard
**Shows** the risk engine: susceptibility ranking, cascade graph, scenario matrix, completeness
heatmap and the validation panel.

**Say:** "The validation panel reports a −83 percent residual. The model under-predicts, we
show it, and we say why."

---

### `/pipeline` How it works
**Shows** the eight-stage explainer from dataset to decision, plus the full dataset table. This
is the page for a non-technical visitor.

---

### `/trace` Raw traces
**Shows** every run as its raw event log: tool calls with arguments, results, retries, claims,
verification, decision, action.

**Say:** "Receipts. Nothing here is reconstructed for the demo."

---

### `/build` Build log
Phase-by-phase record of what was built and verified.

---

## Part 2 — The voice agent

**Yes, it exists and it works. It is not wired into the alert pipeline.** Be precise about
this, because it is the easiest thing to overclaim.

**Where:** `actions/voice.py`, using the `sanket-voice` router lane on Azure `gpt-audio`,
voice `alloy`, with the Nepali script template in `actions/scripts_ne.py`.

**What is real:** it generates genuine spoken Nepali. Verified live:

```
आउटपुट: Timureका बासिन्दाहरू ध्यान दिनुहोस्। बाढीको जोखिम बढेको छ।
        अनुमानित समय 14 मिनेट भित्र पानी आउन सक्छ।
        कृपया तुरुन्त सुरक्षित र अग्लो ठाउँमा सर्नुहोस्। यो एक स्वचालित सन्देश हो।

file:   dist/audio/*.wav   696 KB, 24 kHz mono, 14.5 seconds
```

**What is not real:** the outbound phone call. `VoiceCallResult.dialler_simulated = True`. We
synthesise the audio; we do not dial a telephone.

**How to demo it:**

```bash
.venv/bin/python3 -c "
from actions.voice import generate_call, call_summary
r = generate_call('Timure', 14, 'demo')
print(call_summary(r))"
# then play the wav it prints
```

**Say:** "The audio is real Azure text to speech in Nepali. The dialler is not connected —
that is a telco integration, not a research problem. Voice matters here because literacy is not
universal and a spoken warning reaches people a text message does not."

**Honest caveat to volunteer:** `generate_call` is called from a test, not from the Actor. It
is a working capability that has not been wired into the release path, because the release path
currently goes to WhatsApp.

---

## Part 3 — What is real, what is not

### Real
Every dataset. The DEM stage-volume, breach hydrograph and Saint-Venant router. The Bayesian
prediction. The failover, verified by invalidating live API keys. The Verifier's four checks.
WhatsApp delivery through Twilio with stored message SIDs. The gate's identity and timestamp
record. Nepali voice synthesis. The MCP server's tool schemas.

### Synthetic, and declared
Institutional contact numbers are non-routable; only the approver's is real. SMS goes to a
simulated gateway. The voice dial-out is simulated. The replay clock compresses elapsed time
only — every granule, DEM read and solver output it drives is real and filtered by an as-of
date. The scenario grid is real solver output but always typed `scenario`.

### Known limitations, volunteer them
The DEM predates the event by nine years. Population is modelled, not counted. The source
catchment is in China with no gauges. A lake can form and drain between two satellite passes.
The routing under-predicts by 83 percent against observed extent.

---

## Part 4 — Selling it, in simple words

### The one-line answer

> **"We don't sell the software. We sell the watching."**

A ministry that buys software has to maintain it, and it rots in a year. A hydropower company
that buys *a service that watches their valley* renews it every year, because the risk does not
go away.

**And the alert to a villager is always free. Never charge for that.**

### Why they pay: the loss is enormous, the fee is not

The August event, in this one corridor, using the replacement costs already in our code:

| What was lost | Cost |
|---|---|
| 726 buildings destroyed or badly damaged | NPR 65 – 174 crore |
| 39 bridges washed out | NPR 136 – 468 crore |
| **Total direct asset damage** | **NPR 202 – 642 crore** |

That is roughly **USD 14 to 46 million**, in one valley, in one night.

Now the other side. Running the system costs almost nothing. Our most expensive full agent run
was **NPR 0.73**. Even at ten deep runs a day, that is **NPR 2,664 a year** in compute. The
detection tier costs zero because it calls no model at all.

**So the real cost is people, not machines.** One engineer on call, data agreements, and
keeping the pipeline alive.

### The price list

Not validated with a customer yet, so say that. But this is the shape:

| Who | What they get | Per year |
|---|---|---|
| **Hydropower operator** (one plant) | Corridor watch, machine feed into their control room, on-call | **NPR 15 – 40 lakh** |
| **District or province** (one corridor) | Full system, alert delivery, officer training, gate integration | **NPR 40 – 80 lakh** |
| **National** (all 8 basins) | Everything, plus a second on-call engineer | **NPR 3 – 5 crore** |
| **Insurer or reinsurer** | Exposure model and scenario grid as a data licence, no alerting | **NPR 20 – 50 lakh** |

### Why these numbers are defensible

- **NPR 25 lakh a year to a hydropower operator** is roughly one senior engineer's salary. For a
  plant worth billions, sitting below **252 MW of exposed capacity** in this corridor alone, that
  is a rounding error against one week of lost generation.
- **NPR 60 lakh a year for a district** is less than **one fifth of one bridge**. Thirty-nine
  bridges went in a night here. If it prevents a single bridge loss once a decade it has paid for
  itself many times.
- **NPR 4 crore for the nation** is about **USD 285,000**. That is an ordinary line item in a
  World Bank, ADB or Green Climate Fund resilience programme. It is not a big ask in that room.

### Who pays first, in order of how real the money is

**1. Hydropower operators.** This is the anchor. They have assets in the water, they already pay
for insurance and downtime, and the conversation is a simple return on investment. Start here.

**2. Government, funded by donors.** DHM and NDRRMA are the operational owners, but the money
comes from a donor resilience programme, not core budget. Sell the corridor, let the donor pay.

**3. Insurance and reinsurance.** They need exposure numbers and base rates to price Himalayan
flood risk. That is a data licence, higher margin, no on-call burden.

**4. Road and bridge authorities.** Same routing and exposure layers, used for siting new
assets rather than for warning.

### Why not the other models

- **Sell it once as software.** No. Nobody maintains it, and in a year it is dead.
- **Per user, like normal SaaS.** No. The users are villagers who pay nothing, and there are
  only a handful of district officers.
- **Charge per API call.** No. A full run costs NPR 0.73. There is no business in metering that.
- **Sell the MCP server or the API.** These are **ways to deliver, not things to sell**. It is a
  good answer to "how does this integrate with what we already run", but nobody writes a cheque
  for an endpoint.

### If they push on the price

> "We have not tested pricing with a customer, so treat these as a starting point. But the anchor
> is simple: one bridge in this corridor costs NPR 3.5 to 12 crore to replace, and thirty-nine
> went in one night. Anything we charge below the price of a single bridge is easy to justify,
> and procurement will negotiate us down from there."

### The closing line

> "Watching one more valley costs us under a rupee a run. What costs money is people and the
> promise to answer the phone at 3 a.m. So we sell a service contract to the people who own
> things in the flood path, and the warning to the family living there stays free — because a
> warning you have to pay for is not a warning."

## Part 5 — The questions that come up most

**"Is the AI making up the numbers?"**
No. Sixteen Python tools compute; the model chooses which to call and reads what returns. Every
number in a claim carries a resolvable evidence ref.

**"Is there real machine learning?"**
Yes, but not in the prediction. Sentence-transformer embeddings drive the Verifier's
contradiction retrieval, Otsu thresholding is refitted per scene, and the LLMs choose tools. The
probability itself is Bayesian arithmetic with zero model calls, deliberately, because there is
no training set at this sample size and a hydrologist has to be able to argue with it.

**"What happens when the AI is down?"**
Azure falls back to Groq, Groq falls back to a deterministic run with no model at all, and that
falls back to the last known good status with its age shown. Tested by invalidating live keys.

**"Who is accountable if it is wrong?"**
The district officer who signed. The gate records the decision, the timestamp and the contact.
The system cannot release above YELLOW on its own, by construction, not by policy.

**"What would you build next?"**
River-stage sensors in the corridor. Every arrival time in this system is modelled and
uncalibrated against a real hydrograph. Six gauges would turn the largest source of uncertainty
into a measurement.
