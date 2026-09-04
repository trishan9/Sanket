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

## Part 4 — The commercial answer

If a judge asks what you would sell, **do not say "the software"**. Villagers cannot pay, and a
one-off licence to a ministry rots within a year because nobody maintains it.

### The answer

> "We would not sell the software. We would sell a **monitored corridor**: a per-corridor annual
> subscription covering the data pipeline, the compute, the model updates and an on-call
> guarantee. The public alerts are free forever and always will be. The people who pay are the
> people with assets in the flood path."

### Who actually pays, in order of how real the money is

**1. Hydropower operators — the anchor customer.**
This is where the commercial case is hardest. Our own corridor cells show **252 MW of exposed
hydropower**. A single outburst destroys intake structures, penstocks and years of revenue. An
operator already spends real money on insurance and downtime. Selling them corridor monitoring
with a machine-readable feed into their SCADA is a straightforward return-on-investment
conversation, not a public-good appeal.

**2. The state, donor-funded.**
DHM and NDRRMA are the operational owners, but they will not fund it from core budget. The
route is a World Bank, ADB, UNDP or Green Climate Fund resilience programme, where early
warning is already a funded line item. Price per corridor per year, scaling as corridors are
added.

**3. Insurance and reinsurance.**
The exposure model, the scenario grid and the historical base rates are exactly the inputs a
reinsurer needs to price Himalayan flood risk. That is a data product, not an alerting product,
and it carries a very different margin.

**4. Infrastructure planning.**
Road and bridge authorities siting new assets need the same routing and exposure layers.

### Why not the alternatives

- **Per-seat SaaS:** wrong shape entirely. The end users are villagers who pay nothing, and the
  operator count is a handful of district officers.
- **API metering:** the value is not in API calls. Our most expensive full agent run cost
  **NPR 0.73**. Metering that is not a business.
- **MCP server / API:** these are **distribution channels, not the product**. The MCP server
  means another agent can query the corridor tools; that widens reach and it is a good answer to
  "how does this integrate", but nobody buys an MCP endpoint.

### The line to close on

> "The marginal cost of watching one more valley is almost nothing — a full agent run costs
> under one rupee. The cost is people, data agreements and the on-call promise. So the business
> is a service contract with the people who own assets in the flood path, and the warning itself
> stays free, because a warning someone has to pay for is not a warning."

### If pushed on numbers

Be honest that pricing is not validated. The defensible framing is comparative:

> "We have not tested pricing. But the reference point is what one outburst costs. In this
> corridor the August event destroyed 677 buildings and washed out 39 bridges. Annual monitoring
> priced anywhere below the cost of a single bridge replacement is trivially justified, and we
> would start there and let procurement argue it down."

---

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
