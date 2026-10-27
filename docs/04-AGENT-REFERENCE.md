# 04 — SANKET Agent Reference

Six agents. What each does, which datasets it touches, how they communicate, how they are orchestrated, and how it all maps to the hackathon brief.

---

## 1. At a glance

| # | Agent | Provider · Model | Fires when | Its one job |
|---|---|---|---|---|
| 1 | **SCOUT** | Groq · `groq/compound` | Weekly national sweep | Decide which corridors deserve a close watch |
| 2 | **WATCHER** | Groq · `gpt-oss-20b` (Tier 2 only) | Tick, and every new granule | Decide whether anything is worth investigating |
| 3 | **INVESTIGATOR** | Azure · `gpt-5.5` | Watcher says `investigate` | Work out what happened and what it means downstream |
| 4 | **VERIFIER** | Azure · `grok-4.6` | Investigator finishes | Decide whether the conclusions are supported |
| 5 | **EXPLAINER** | Groq · `gpt-oss-120b` | Verifier finishes | Make the decision legible — attribution, counterfactuals, three audiences |
| 6 | **ACTOR** | deterministic + Azure `gpt-audio` | Explainer finishes | Make something change in the world |

**Why six and not more.** Two signals done deeply beats six done shallowly, and a hardcoded chain with a model filling in text is automation, not agency. Six agents, one of which runs a genuinely open tool loop, is the honest version. We considered and cut a separate Recommendation Agent (folds into Explainer), a Land-cover Agent (irrelevant at 5,600 m), Drought/Fire/Heat Agents (out of scope) and a standalone Satellite Agent (Earth observation is a *tool layer*; three agents use it).

---

## 2. SCOUT — national breadth

**Role:** why this is a national system and not one corridor with ambition.

Watcher goes deep on active corridors every fifteen minutes. Scout goes wide across all of them, slowly.

Once a week it sweeps the **47 potentially dangerous glacial lakes** identified in the ICIMOD/UNDP assessment across the Koshi, Gandaki and Karnali basins — 21 in Nepal, 25 in China, 1 in India — plus the wider inventory. For each it computes a coarse change signal, ranks the basins, and **promotes or demotes corridors between watch tiers.**

| Tier | Cadence | Corridors |
|---|---|---|
| Active watch | 15 min | Open anomaly or recent event |
| Standing watch | 6 h | Elevated change signal |
| Survey | weekly | Everything else |

**The daemon reads the tier. The system allocates its own attention across the country** — a form of agency Watcher does not have.

### Datasets

| Dataset | Use |
|---|---|
| **ICIMOD glacial lake + PDGL inventory** (DOI 10.26066/RDS.1971946 / 1971950) | The population Scout sweeps |
| **OPERA DIST-ALERT-HLS v1**, national extent | Coarse disturbance signal per basin |
| **Sentinel-2 L2A**, low-frequency composites | Lake area change at survey cadence |
| **HMAGLOFDB** (697 GLOFs, 1833–2022) | Recurrence base rates — basins with history start weighted higher |
| **Copernicus DEM GLO-30** | Coarse downstream screening beyond the HMA 8 m footprint |
| **WorldPop + OSM settlements** | How many people sit below each lake |

**Why Groq:** 47 basins in one sweep is the highest-volume model work in the system. It runs on **our own quota**, not the key shared by fifteen teams, and `groq/compound` carries the largest TPM headroom available to us.

### Communicates via

`basin_tiers` records. It never triggers an investigation directly — it changes how often Watcher looks. Decoupled on purpose: a mistaken promotion costs a few extra ticks, not a false alarm.

### Also produces

A **standing exposure ranking** across all 47 PDGLs, so the board's national panel shows not only which corridors are changing but which are most exposed if they do.

---

## 3. WATCHER — the standing sentry

**Role:** the only reason the system is autonomous at all.

| Tier | Frequency | Model calls | Does |
|---|---|---|---|
| **0 — Tick** | per basin tier | **zero** | Ask NASA CMR whether a new OPERA granule was published over the watched tiles since the last check. Check DHM stage thresholds. Check whether an open anomaly is due for re-inspection. |
| **1 — Change detection** | on a new granule | **zero** | Water extent and disturbance area against a rolling 14-observation baseline the system computed itself, as a z-score against that baseline's own variance |
| **2 — Classification** | on change outside the band | **one small call** | Constrained output: `investigate \| artefact \| seasonal \| insufficient_data` |
| **3 — Handoff** | on `investigate` | — | Write a job to the work queue |

Tiers 0 and 1 make **zero LLM calls** — asserted in a test.

**Why Tier 2 exists.** Radar layover and shadow in a steep valley, a wet-snow backscatter drop, an orbit-geometry difference between passes — all look like change and are not. A few hundred tokens stops the expensive path firing on noise. This is the "earn a small footprint" property, built in rather than optimised for later.

### Datasets

**OPERA DSWx-S1** (primary, via NASA CMR + `earthaccess`) · **OPERA DIST-ALERT-HLS v1** · its own **`baselines` table** — *the system computes what "normal" is; it is not hardcoded* · **DHM river watch** (weakest trigger, and we say why) · the **corridor registry**.

### Communicates via

An `InvestigationJob` written to a SQLite work queue. Queue-based, not in-process, so a crash mid-investigation loses nothing.

---

## 4. INVESTIGATOR — the reasoning

**Role:** where the agency lives.

Receives a **goal, not a script**:

> Characterise the anomaly at this location. Determine whether it represents an impoundment. If so, determine the downstream consequence and the exposed population. Establish confidence. Do not state anything the evidence does not support.

Chooses its own tools, in its own order, up to ten iterations. **The sequence is not hardcoded**, and that is checkable in the trace.

### Twelve tools and their datasets

| Tool | Datasets |
|---|---|
| `search_granules` | NASA CMR catalogue |
| `detect_water_change` | OPERA DSWx-S1 + `baselines` |
| `detect_disturbance` | OPERA DIST-ALERT-HLS v1 |
| `lake_area_series` | Sentinel-2 L2A via Planetary Computer STAC; OmniCloudMask; OmniWaterMask; our MNDWI+Otsu detector |
| `precip_percentile` | GPM IMERG or CHIRPS vs a 20-year climatology |
| `stage_volume` | **NASA HMA 8 m DEM**, tiles 642/643/675/676 |
| `breach_hydrograph` | derived from stage-volume |
| `route_flood` | HMA 8 m DEM + the precomputed scenario grid (`swe2d_torch`, `route1d`) |
| `exposure_at` | OSM/HOT buildings, roads, bridges, health, education, hydropower; WorldPop; HDX `hot_flood_npl` |
| `precedent` | HMAGLOFDB; ICIMOD PDGL inventory; BIPAD extracts |
| `science_lookup` | ChromaDB `science` collection |
| `write_status` | writes the board — **the autonomous consequence** |

Gated — may request but not execute: `voice_call`, `send_sms`, `send_whatsapp`.

### Divergent paths — the evidence for signal 01

| Situation | Sequence it typically chooses | Steps |
|---|---|---|
| New water at a known lake | lake series → precip percentile → precedent → stage-volume → breach → route → exposure | 7–8 |
| Disturbance, no water signature | disturbance → cross-sections → stage-volume returns ~0 → **stops.** No routing, because there is nothing to route. | 3–4 |
| Ambiguous under heavy cloud | radar → optical fails on cloud → precedent → concludes insufficient, escalates | 3–4 |

Capture two as traces and show them side by side. That is the answer to *"what did the model decide that you didn't hardcode?"*

### The hard rule

**The LLM never computes a number.** Every quantity comes from a deterministic Python function. The model chooses which function, with what arguments, and interprets what comes back.

### Communicates via

A typed `EvidenceLedger`. Not prose. Every entry carries a signed provenance envelope: source, granule IDs, acquisition time, method, `as_of` filter, uncertainty, `claim_type`.

### Boundaries

- May not state that an outburst is likely or imminent — 10–30 m imagery cannot establish that
- May not attribute anything to climate change; it may report a value exceeded its baseline, and the sentence stops
- All routing outputs are `claim_type: scenario`, never `prediction`, with the parameter set attached
- Must report that the DEM predates the event

---

## 5. VERIFIER — the one that refuses

**Role:** the agent we name in the pitch.

| Check | Question |
|---|---|
| `check_independence` | Do two supporting sources share an `independence_group`? If DHM and ICIMOD both worked from the same Chinese-supplied imagery, that is **one** line of evidence, not two. |
| `check_temporal_validity` | Does any evidence post-date the `as_of` cutoff? |
| `check_claim_licensing` | Does the evidence type support the claim type? An observation does not license a scenario claim. |
| `detect_contradiction` | Surface conflicts. **Do not resolve them.** |

```python
class Claim(BaseModel):
    statement: str
    claim_type: Literal["observation","correlation","model_output",
                        "scenario","hypothesis","recommendation"]
    supporting: list[EvidenceRef]
    contradicting: list[EvidenceRef]
    independence_groups: set[str]
    confidence: Literal["high","medium","low","insufficient"]
    veto_reason: str | None = None
```

**Runs on `grok-4.6`, a different model family from the planner.** A model checking its own work is not a check — a thirty-second answer in Q&A that reads as engineering judgement.

**Enforced in code, not the prompt:** reject any `Claim` whose `statement` was not already in the ledger. It may lower confidence and veto. It may never author a claim.

### Datasets

| Source | Purpose |
|---|---|
| **The layer registry** | `independence_group`, `confidence_tier`, and the `cannot_tell_you` list for every contributing layer |
| **ChromaDB `events`** | Contradicting reports, under a hard `published_ts <= as_of` filter — including the geopera reconstruction **and its retracted earlier version**, tagged `claim_type: retracted` |
| **ChromaDB `science`** | Whether a method claim is supported by published work |
| **The rejection log** | How many records the date firewall excluded this run |

### The live test case

DHM and ICIMOD concluded from satellite imagery that the 26 August event was a supraglacial-lake GLOF. An independent stereo-elevation reconstruction concluded no pre-existing lake drained — and **publicly retracted its own sediment-volume figure** after finding a parallax error.

**Expected behaviour:** veto the cause claim, emit `insufficient — no claim issued`, and add that the downstream exposure assessment does not depend on which mechanism is correct.

### Communicates via

`VerificationTable` + `StatusDecision` (`NORMAL | WATCH | ALERT | INSUFFICIENT`).

---

## 6. EXPLAINER — the XAI layer

**Role:** make the decision legible. Not a summariser — an explanation engine.

The system is about to phone people and tell them to leave their homes. **A district officer cannot approve what they cannot interrogate.** Explainer is what makes the gate a decision rather than a rubber stamp.

### Four artifacts

**1. Decision attribution — deterministic, not guessed.** The status level is a function of four terms: change magnitude (z-score), minimum lead time, exposure count and confidence. Explainer **decomposes that actual function** and reports each term's contribution.

```
STATUS: WATCH
  change magnitude   z=3.4    contribution  +0.41
  minimum lead time  14 min   contribution  +0.33
  exposure count     916      contribution  +0.19
  confidence         medium   contribution  −0.07
```

Computed in Python from the real decision function. The LLM renders them; it does not produce them.

**2. Counterfactuals — from the precomputed scenario grid.** Instant and real.

> If the impounded volume were 1.5 Mm³ rather than 2.5, Timure's lead time goes from 14 to 26 minutes and the status drops to NORMAL.
> If the breach were progressive over 3 hours rather than partial over 30 minutes, no settlement falls below the 30-minute threshold.

**The single most useful thing on the approver's screen** — it tells them how close to the edge the decision is.

**3. The flip point.** The minimum change in each input that would flip the status.

> Status flips to NORMAL if volume falls below 1.8 Mm³, or if exposure is over-estimated by more than 34%.

Directly actionable: it tells DHM which uncertainty actually matters, and aggregated across corridors it becomes a **monitoring-priority list** — where to place instruments.

**4. What would change my mind.** The Verifier's evidence gaps, ranked by how much closing each would move confidence.

> A cloud-free optical scene over the impoundment would move confidence from medium to high.
> The contested cause of the 26 August event would not change this assessment either way.

That last line is the honest one: it tells the officer which open questions are irrelevant to their decision.

### Three registers

| Audience | Output | Constraint |
|---|---|---|
| **Public board** | Plain language, Nepali and English | Two or three sentences, including what the system refused to conclude |
| **Approver gate screen and WhatsApp** | Attribution, counterfactuals, flip points, evidence gaps, provenance links | Technical. Every number links to its source. |
| **Voice, SMS, WhatsApp to residents** | Nepali, ~22 s, one settlement, one number, one action | No hedging, no jargon. **Template with slots, never free composition.** |

**Same evidence, three renderings.** A test compares the numeric claims across all three and fails on divergence — the public version cannot quietly soften a caveat, and the voice version cannot add certainty.

### Datasets

The `VerificationTable` and `EvidenceLedger` · the precomputed scenario grid · the layer registry (`cannot_tell_you` surfaces directly in explanations) · Nepali script templates.

**Why Groq:** three renderings plus attribution on every escalation is volume work on a fixed input — exactly the shape that belongs on our own quota.

### The Analyst Sandbox

A `smolagents` `CodeAgent` with `geopandas`, `rasterio` and a **read-only** DuckDB connection to the gold layer, surfaced as an Ask panel **on the gate screen only.** For approver follow-ups no tool covers: *"what if exposure is over-estimated by fifty percent?"*, *"which settlements have under twenty minutes in every scenario?"*

Guardrails: read-only · no network · no filesystem writes · 10-second timeout · results tagged `claim_type: model_output` · **cannot write status, trigger a notification, or influence a gate decision.** Deleting it leaves every other test green.

### Boundaries

- May not introduce a fact not in the ledger. Code-level enforcement, same as the Verifier.
- May not omit a veto. If the Verifier issued no claim, every rendering says so.
- Voice and SMS scripts are **template-with-slots**. An LLM improvising an evacuation instruction is not something to ship.

---

## 7. ACTOR — consequence

**Role:** without this, the whole thing is a very good assistant.

### Autonomously, at WATCH

- `write_status(settlement, level, evidence)` — a record is written, **the public board changes**
- Run record written to `runs`
- Anomaly updated or closed
- **DHM's duty channel notified** — the operator, not the public

### Only after a human says yes, at ALERT

- Assembles the call list from the institutional contact table
- Generates real Nepali audio with `gpt-audio` / Azure TTS, arrival time interpolated
- Drafts the 140-character SMS and the three WhatsApp tiers
- Renders the inundation map image for WhatsApp
- Sends the **gate request over WhatsApp** to the named DDMC duty officer with attribution, counterfactual, before/after image and `Reply APPROVE <run_id>`
- Writes a `gates` record with a deadline

**Nothing goes out until approval is recorded with identity and timestamp.**

### The human checkpoint

> The agent may never place a voice call, send an SMS or WhatsApp message, or raise public status above WATCH without a named district officer approving.

A false public flood warning empties a valley, disrupts livelihoods, and burns the trust the next real warning depends on. Board updates are reversible and cheap; a warning is neither.

**The gate over WhatsApp** is deliberate: a duty officer at 03:00 has a phone, not a laptop.

### Datasets

**Institutional contact table** — synthetic, declared, matching the real distribution (DDMC duty officer, DHM divisional hydrologist, local administration, hydropower operator, police post, health post, school, community focal point), non-routable numbers · **`subscribers`** with `opted_in_at` and `stopped_at` · **`notifications`** for cooldown, checked *before* the gate · **`gates`** for approver identity and decision · OSM/HOT settlements · the scenario grid for arrival times.

### Communicates via

SQLite writes (board, notifications, gates), Twilio (WhatsApp, and the inbound webhook for approvals), TTS audio files, SMS payloads. Every action logged to the trace with its result.

---

## 8. Orchestration

### The rule

**Agents do not talk to each other. They hand typed artifacts through shared state.**

```
  SCOUT ──weekly──► [ basin_tiers ] ──────────┐
                                              │ sets cadence
   TRIGGER ─────► WATCHER ◄────────────────────┘
   cron              │ writes InvestigationJob
   CMR granule       ▼
   stage         [ SQLite work queue ]        ← survives a crash
   replay clock      │ worker dequeues
                     ▼
                INVESTIGATOR ──► [ EvidenceLedger ]        typed Pydantic
                     │ (twelve tools)     ▼
                     │                VERIFIER ──► [ VerificationTable ]
                     │                                [ StatusDecision ]
                     │                                     ▼
                     │                                EXPLAINER ◄── Sandbox
                     │                     ┌───────────────┴───────────────┐
                     │               [ PublicNote ]  [ EvidencePack ]  [ Scripts ]
                     │                     └───────────────┬───────────────┘
                     │                                     ▼
                     │                                  ACTOR
                     │                             ┌───────┴───────┐
                     │                       autonomous          gated
                     │                       board write   → [ gates ] → WhatsApp
                     │                                              → human
                     ▼                                                 │
               [ TRACE — append-only, all six agents ] ◄────────────────┘
```

### Why this shape

**Scout is decoupled from everything.** It writes a tier, nothing more. A mistaken promotion costs extra ticks, never a false alarm.

**A queue sits between Watcher and Investigator.** Detection runs on the tier cadence; investigation takes tens of seconds. The queue decouples the clocks and means a crash re-queues from the last completed tool call rather than losing the finding.

**Handoffs are typed, not conversational.** Agent-to-agent chat is where hallucination compounds. The Verifier receives a `Ledger`; the Explainer receives a `VerificationTable`. Neither can be talked into anything the previous agent merely asserted in prose.

**Explainer sits between Verifier and Actor on purpose.** Nothing reaches a human — public, approver or resident — that has not been through both the veto and the explanation. An unexplained alert is not an alert anyone can act on.

**Flow is one-way.** No agent calls backwards. If evidence is thin the Verifier says so and escalates rather than re-running the Investigator. That is what keeps the trace linear and readable.

**All six write the trace**, append-only, one file, rendered at `/trace`. Deliverable 2 and the debugging surface. Written in Phase 0, before the loop exists.

### Memory

| Scope | Where | What |
|---|---|---|
| Within a run | `EvidenceLedger` | Every tool result with provenance, every claim, every veto |
| Across runs | SQLite | `basin_tiers` · `baselines` · `anomalies` · `runs` · `notifications` · `gates` · `subscribers` |

**The second run is verifiably different.** It matches an anomaly fingerprint rather than opening a new one, compares against a baseline it computed itself, respects the notification cooldown, and cites three-run growth as evidence when it sees it. Scout's tier assignments persist across weeks.

### Bounds

`MAX_STEPS = 10`, hard · wall-clock timeout per run · token counter from hour one · response cache keyed on message hash · exponential backoff with jitter · **no autonomous loop left running unattended** · every LLM call through `agent/router.py`, enforced by a lint rule.

---

## 9. Mapped to the hackathon brief

### The six agentic signals

| Signal | Agent | Evidence in the demo |
|---|---|---|
| **01 Goal, not script** | Investigator | Two traces side by side with different tool sequences. Nothing about the order is hardcoded. |
| **02 Uses tools** | Investigator, Actor | Twelve tools plus voice, SMS and WhatsApp. The model picks which and with what arguments. |
| **03 Plans across steps** | Investigator | Bounded loop, `MAX_STEPS = 10`. The trace shows a real 504, a backoff and a successful retry. |
| **04 Remembers** | all six, via SQLite | Second run recognises `anom_07` as open, cites three-run growth, respects cooldown. Scout's tiers persist. |
| **05 Starts by itself** | **Scout + Watcher** | Weekly sweep, cron tick, CMR granule event. **No human input path exists in the codebase.** |
| **06 Action has consequence** | **Actor** | Status written, board changes, DHM duty channel notified, **real WhatsApp messages with the flood map on real phones**, Nepali voice calls, SMS, case escalated to a named officer. |

### The human checkpoint

Named, built, demoed holding — **over WhatsApp**, where a duty officer actually is. The approver sees Explainer's full pack. Approval is recorded with identity and timestamp. Unauthorised replies are logged and ignored.

### The delete-the-words test

> *A system that watches a glacier valley in Tibet by satellite, works out how much water a landslide dam is holding, calculates when it would reach each village downstream, and messages the ward secretary in Nepali with a map before the water arrives.*

No occurrence of "AI" or "agent". Still describes something someone would use on Monday.

### The four bad-day properties

| Property | Carried by |
|---|---|
| **Degrade, don't die** | The router: Azure → Groq → local Ollama → deterministic mode → last known good, each step stamped in the trace. Watcher keeps running on radar when optical is cloud-blind. **Demonstrable by revoking one key live.** |
| **Reach the last person** | Actor + Explainer: Nepali voice over cellular, 140-char SMS, WhatsApp with the map, 4 KB board over 2G |
| **Earn a small footprint** | Scout's tiering and Watcher's four tiers — 99% of activity costs nothing. Cost per run in NPR, split by provider. |
| **Say how sure you are** | Verifier's confidence and veto; **Explainer's attribution, counterfactuals and flip points** |

### The rubric

| Criterion | Where the marks come from |
|---|---|
| **Innovation (20)** | A standing watch where none exists. An agent that refuses. XAI that shows the flip point, not a confidence badge. Watching *blockages* rather than lakes. The gate over WhatsApp. |
| **Technical (25)** | Six signals, four deep. Unsanitised trace, rendered. Four-tier cost design. Different model family for the critic. Dual-provider gateway with cross-provider failover. |
| **Impact (20)** | Lead time computable per settlement. Standing preparedness before any alert. Validation against Copernicus EMS EMSR927. The Bad Day. |
| **Scalability (20)** | A corridor is a YAML file — open it on stage. Scout already sweeps all 47 PDGLs. Free data end to end. Public infrastructure, not a business. |
| **Presentation (15)** | Live trigger nobody touches. The gate holding. Real WhatsApp on judges' phones. Nepali audio in the room. The real-vs-mocked list volunteered. |
| **+5 Resilience** | Nepali voice, SMS and WhatsApp demonstrated live, plus the throttled 2G board |
| **+3 Open contribution** | `sanket-mcp` (twelve tool schemas over MCP) and the corridor lakehouse on HuggingFace with a per-layer licence table |

### Q&A

| Question | Answer |
|---|---|
| *What did the model decide that you didn't hardcode?* | The tool sequence. Two traces, different anomaly types, different paths. |
| *What happens on the second run?* | It recognises the anomaly as already open, checks whether it grew, and does not re-contact wards inside the cooldown. It's in the run history on the board. |
| *What does one run cost?* | NPR 3.80, split Groq 2.10 / Azure 1.70. Everything to `gpt-5.5` would be roughly six times that. |
| *Why two providers?* | Different scarcity. The hackathon key is shared by fifteen teams; our Groq quota is ours. Frontier judgement and audio on theirs, volume on ours — and we get cross-provider failover for free. |
| *Why LiteLLM?* | One router, per-deployment rate limits, automatic cooldown on 429, cross-provider fallback chains, per-call cost tracking. `simple-shuffle` with tpm/rpm set, not usage-based routing — their own docs flag the Redis overhead. |
| *Why not LangGraph or CrewAI?* | Six agents in a pipeline with one open tool loop is not a graph problem. We wrote the loop so we can explain every line. We do use smolagents, in exactly one place where its strength matters. |
| *Is the XAI real or is the model narrating?* | Attribution comes from decomposing the actual decision function. Counterfactuals come from the precomputed grid. The model renders them; it does not produce them. |
| *What is mocked?* | Dialler and SMS gateway simulated; contacts synthetic; scenario grid precomputed; replay clock simulated. **WhatsApp is real, audio is real, satellite data is real, DEM is real, agents run unmodified.** |
| *What would you never let it do on its own?* | Contact anyone, or raise public status above Watch. A false warning empties a valley and burns the trust the next real warning depends on. |
| *Isn't the dashboard the anti-pattern you were warned about?* | It would be if it waited. It doesn't — the agents already looked, decided, explained and wrote the status. The board is where the system publishes. |
