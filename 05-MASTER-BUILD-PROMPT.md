# 05 — SANKET MASTER BUILD PROMPT

Paste this whole document as your first message to the coding agent. Self-contained. Replaces all earlier build prompts.

---

## ROLE

You are the lead engineer building **SANKET — Standing Watch**, a national glacial-hazard watch for Nepal.

It is an **autonomous agent system**, not an application. It runs itself on a schedule and on satellite-data events. Nobody types a question. Nobody presses a button. It watches, decides, explains, and acts.

**Fifteen phases, in order.** No skipping, no stubbing, no "simplify for now". A phase is done when its exit criteria pass, not when it looks done.

---

## FIRST ACTION — PLAN, THEN STOP

1. Read this document in full.
2. Read `01-PRODUCT-SPEC.md`, `02-TECHNICAL-SPEC.md`, `03-EVIDENCE-AND-IMPACT.md` and `04-AGENT-REFERENCE.md` if present.
3. Produce **`PLAN.md`**: your interpretation in ~300 words; the fifteen-phase breakdown with deliverables, file paths, tools, exit criteria and effort per phase; pinned dependencies; numbered assumptions; open questions; anything here you think is wrong, stated plainly.
4. Produce **`MANUAL_DOWNLOADS.md`**, initial **`PROGRESS.md`** and **`progress.json`**.
5. **Stop and wait for approval before Phase 0.** Stop after each phase for confirmation.

---

## THE SYSTEM

### One sentence

> **Our agent helps Nepal's disaster authorities warn communities below glacial lakes without anyone watching a screen.**

### National scope

Designed for the **Department of Hydrology and Meteorology** and **NDRRMA**, with District Disaster Management Committees holding the approval gate.

The ICIMOD/UNDP assessment identified **47 potentially dangerous glacial lakes** across the Koshi, Gandaki and Karnali basins — 21 in Nepal, 25 in China, 1 in India. ICIMOD counts more than 25,000 glacial lakes across the Hindu Kush Himalaya. None is under continuous automated watch today.

**The architecture is national. One corridor runs at high cadence; all 47 are swept weekly.** A corridor is a YAML file — you must be able to open it on screen and prove adding one is a data operation, not a code change.

### The live corridor

Lhende Khola → Bhotekoshi → Trishuli, Rasuwa and Nuwakot.

- **26 Aug 2026, ~08:37:** ~600 m of glacier ice and rock detached from ~5,600 m on the Langtang Himal into the upper Lhende. USGS reclassified the seismic signal from M4.4 earthquake to **M5.2 landslide-type event**. The debris dammed the river; the dam failed; the Trishuli rose up to 9 m in 30 minutes. Bodies recovered across seven districts. **Casualty figures moved daily and are provisional — always cite with a date.**
- **8 Jul 2025:** GLOF from Jilong County, Tibet destroyed the Miteri Bridge.
- **Neither was rainfall-driven.** No rain reported at Rasuwa district HQ during either.
- **27–28 Aug 2026:** a barrier lake formed, estimated by China's Ministry of Water Resources at ~1.5–2 million m³ with up to ~3 million more possibly incoming. It began overflowing on the 28th. **It is still there.**

### The precursor

ICIMOD time-series analysis documents a lake at the **Purepu Glacier, ~35 km upstream**, forming and draining within about a week in **July 2023**, widening in **December 2024**, and growing significantly in **June 2025** — weeks before the July 2025 GLOF. Three years of satellite-visible change in a corridor that then flooded twice. Every observation was free and public.

---

## THE SIX AGENTIC SIGNALS

| Signal | Implementation |
|---|---|
| **01 Goal, not script** | The Investigator gets a goal and twelve tools and chooses its own sequence. **Never hardcode the tool order.** Different anomaly types must produce visibly different paths in the trace. |
| **02 Uses tools** | Twelve tools plus voice, SMS and WhatsApp. The model chooses which and with what arguments. |
| **03 Plans across steps** | Bounded loop, `MAX_STEPS = 10`. Failures caught, backed off, retried. The trace must show a real failure and a real recovery. |
| **04 Remembers** | SQLite state. Within a run: the evidence ledger. Across runs: open anomalies, notifications, self-computed baselines, Scout's basin tiers. **The second run must behave differently from the first, verifiably.** |
| **05 Starts by itself** | A daemon. Weekly Scout sweep, tick per basin tier, new OPERA granule published to NASA CMR, river-stage threshold. **No human input path exists.** |
| **06 Action has consequence** | Status written, board changes, DHM duty channel notified, **real WhatsApp messages with the flood map**, Nepali voice calls, SMS, cases escalated to a named officer. |

## THE HUMAN CHECKPOINT

**The agent may never place a voice call, send an SMS or WhatsApp message, or raise public status above WATCH without a named district officer approving.**

**The gate happens over WhatsApp** — a duty officer at 03:00 has a phone, not a laptop. The request carries attribution, counterfactual, flip point, before/after image, and `Reply APPROVE <run_id>`.

Build it. Demo it holding. Then demo approval arriving and the messages going out.

Reason to state on stage: a false public flood warning empties a valley, disrupts livelihoods and burns the trust the next real warning depends on. Board updates are reversible and cheap; a warning is neither.

---

## PART A — THE SIX AGENTS

| # | Agent | Provider · Model | Fires | Job |
|---|---|---|---|---|
| 1 | **SCOUT** | Groq `groq/compound` | weekly | Sweep 47 PDGLs, assign watch tiers |
| 2 | **WATCHER** | Groq `gpt-oss-20b` (T2 only) | tick + granule | Decide whether to investigate |
| 3 | **INVESTIGATOR** | Azure `gpt-5.5` | on `investigate` | Goal + 12 tools, chooses its own path |
| 4 | **VERIFIER** | Azure `grok-4.6` | after Investigator | Adjudicate, assign confidence, veto |
| 5 | **EXPLAINER** | Groq `gpt-oss-120b` | after Verifier | Attribution, counterfactuals, three registers |
| 6 | **ACTOR** | deterministic + Azure `gpt-audio` | after Explainer | Board, gate, voice, SMS, WhatsApp |

### SCOUT

Weekly sweep of all 47 PDGLs plus the wider ICIMOD inventory. Coarse change signal from OPERA DIST-ALERT national extent and low-frequency Sentinel-2, weighted by HMAGLOFDB recurrence base rates and downstream population from Copernicus GLO-30 + WorldPop. Writes `basin_tiers`:

| Tier | Cadence | Which |
|---|---|---|
| Active watch | 15 min | Open anomaly or recent event |
| Standing watch | 6 h | Elevated change signal |
| Survey | weekly | Everything else |

**The daemon reads the tier. The system allocates its own attention across the country.** Scout never triggers an investigation directly.

### WATCHER — four tiers

| Tier | Frequency | Model calls | Does |
|---|---|---|---|
| **0 Tick** | per basin tier | **zero** | CMR `updated_since` poll, DHM stage, anomaly re-check due |
| **1 Change detection** | on new granule | **zero** | Water and disturbance vs a rolling 14-observation baseline, as a z-score against that baseline's own variance |
| **2 Classification** | on change outside band | one small call | `investigate \| artefact \| seasonal \| insufficient_data` |
| **3 Handoff** | on `investigate` | — | Write a job to the work queue |

**Tiers 0 and 1 make zero LLM calls — assert this in a test.**

```python
def tick(basin: Basin) -> TickResult:
    new_granules = cmr.granules_since(
        products=basin.watched_products,
        tiles=basin.tiles,
        since=state.last_granule_check(basin.id),
    )
    stage_breach = dhm.stage_above_threshold(basin.gauges)
    due = state.anomalies_due_for_recheck(basin.id, now())
    return TickResult(new_granules, stage_breach, due)
```

**Design in one line:** watching is free, deciding is cheap, investigating is expensive, and investigating is rare.

### INVESTIGATOR — the loop

```python
MAX_STEPS = 10

def investigate(goal: str, context: dict) -> Ledger:
    messages = [system_prompt(), user_goal(goal, context)]
    ledger = Ledger(run_id=context["run_id"], as_of=context["as_of"])

    for step in range(MAX_STEPS):
        response = router.completion(
            model="sanket-plan", messages=messages,
            tools=TOOL_SCHEMAS, tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message)
        trace.step(step, message, response.usage)

        if not message.tool_calls:
            ledger.conclude(message.content)
            return ledger

        for call in message.tool_calls:
            if requires_human(call):
                return ledger.escalate(call, reason=gate_reason(call))
            result = execute_with_backoff(call)
            trace.tool(call, result)
            ledger.add(result)
            messages.append(tool_message(call, result))

    return ledger.escalate(None, reason="step limit reached")
```

**Twelve tools:** `search_granules` · `detect_water_change` · `detect_disturbance` · `lake_area_series` · `precip_percentile` · `stage_volume` · `breach_hydrograph` · `route_flood` · `exposure_at` · `precedent` · `science_lookup` · `write_status`. Gated, may request but not execute: `voice_call`, `send_sms`, `send_whatsapp`.

**Divergent paths — signal 01's evidence:**

| Situation | Sequence | Steps |
|---|---|---|
| New water at a known lake | lake series → precip percentile → precedent → stage-volume → breach → route → exposure | 7–8 |
| Disturbance, no water signature | disturbance → cross-sections → stage-volume returns ~0 → **stops** | 3–4 |
| Ambiguous under heavy cloud | radar → optical fails on cloud → precedent → insufficient, escalate | 3–4 |

**The LLM never computes a number.**

**Every tool returns a signed envelope:**

```json
{
  "value": {},
  "provenance": {
    "source": "OPERA DSWx-S1",
    "granule_ids": ["OPERA_L3_DSWx-S1_T45RUL_20260902T..."],
    "acquired": "2026-09-02T04:41:19Z",
    "method": "WTR layer, open-water class",
    "as_of_filter": "2026-09-02",
    "uncertainty": {"pixel_area_m2": 900, "layover_shadow_frac": 0.07}
  },
  "claim_type": "observation"
}
```

`claim_type` ∈ `{observation, correlation, model_output, scenario, hypothesis, recommendation}`. **The renderer must refuse to display a `scenario` in the same visual style as an `observation`.**

### VERIFIER

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

Four checks: `check_independence` (shared `independence_group` means one line of evidence, not two) · `check_temporal_validity` · `check_claim_licensing` · `detect_contradiction` (surface, do not resolve).

**Enforced in code, not the prompt:** reject any `Claim` whose `statement` was not already in the ledger.

**Runs on a different model family from the planner.** A model checking its own work is not a check.

**Live test case:** DHM and ICIMOD concluded a supraglacial-lake GLOF from satellite imagery; an independent stereo-elevation reconstruction concluded no pre-existing lake drained and **publicly retracted its own sediment-volume figure**. Expected: veto, `insufficient — no claim issued`, plus the note that downstream exposure does not depend on the mechanism.

### EXPLAINER

**1. Attribution — deterministic.** Decompose the **actual** status decision function (change magnitude, lead time, exposure, confidence) into per-term contributions. Computed in Python; the LLM only renders.

```
STATUS: WATCH
  change magnitude   z=3.4    contribution  +0.41
  minimum lead time  14 min   contribution  +0.33
  exposure count     916      contribution  +0.19
  confidence         medium   contribution  −0.07
```

**2. Counterfactuals** — from the precomputed scenario grid. *"At 1.5 Mm³ instead of 2.5, Timure gets 26 minutes and the status drops to NORMAL."*

**3. Flip point** — the minimum change in each input that flips the status.

**4. What would change my mind** — Verifier evidence gaps ranked by confidence impact, **including which open questions are irrelevant.**

**Three registers:** `PublicNote` (plain, Nepali and English, includes what was refused) · `EvidencePack` (technical, every number links to source) · `Scripts` (Nepali, ~22 s, one settlement, one number, one action — **template with slots, never free composition**).

**Plus the Analyst Sandbox:** a `smolagents` `CodeAgent` with `geopandas`, `rasterio` and a **read-only** DuckDB connection, on the gate screen only, for approver follow-ups no tool covers. Read-only, no network, no writes, 10-second timeout, results tagged `claim_type: model_output`, **cannot write status, trigger a notification, or influence a gate decision.**

### ACTOR

**Autonomous at WATCH:** `write_status` — record written, board changes. Run record. Anomaly updated. **DHM duty channel notified — the operator, not the public.**

**Gated at ALERT:** assemble the call list, generate real Nepali audio, draft the SMS and three WhatsApp tiers, render the inundation map image, send the **gate request over WhatsApp**, write a `gates` record with a deadline. **Nothing goes out until approval is recorded with identity and timestamp.**

---

## PART B — ORCHESTRATION

**Agents do not talk to each other. They hand typed artifacts through shared state.**

```
  SCOUT ──weekly──► [ basin_tiers ] ───────────┐
                                               │ sets cadence
   TRIGGER ─────► WATCHER ◄─────────────────────┘
   cron              │ writes InvestigationJob
   CMR granule       ▼
   stage         [ SQLite work queue ]        ← survives a crash
   replay clock      │
                     ▼
                INVESTIGATOR ──► [ EvidenceLedger ]
                     │                    ▼
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
                     │                       board write   → [ gates ] → WhatsApp → human
                     ▼                                              │
               [ TRACE — append-only, all six agents ] ◄─────────────┘
```

### State schema

```sql
basin_tiers   (basin_id, tier, score, drivers, assigned_at, assigned_by_run)
baselines     (product, tile, statistic, value, variance, n_obs, computed_at)
anomalies     (anomaly_id, basin_id, fingerprint, location, first_seen,
               status, growth_history, last_investigated, next_recheck)
runs          (run_id, basin_id, agent, trigger, mode, started, ended, steps,
               tokens_azure, tokens_groq, cost_npr, outcome, degradations)
notifications (notification_id, settlement, channel, contact, sent_at,
               run_id, approved_by, cooldown_until, delivery_status)
gates         (gate_id, run_id, action, payload, requested_at,
               approved_at, approver, decision, evidence_snapshot)
subscribers   (contact, channel, settlement, role, opted_in_at, stopped_at)
```

### Behavioural guarantees

**Hysteresis** — escalation threshold above the maintenance threshold. Status does not flap.
**Cooldown** — enforced in `notifications` **before** the gate.
**Fingerprinting** — `hash(location_cell, feature_id, change_signature)`.
**Cold start** — backfill ~24 months of archive; `warming_up` until variance is estimable; the board says why.
**Crash recovery** — SQLite queue; interrupted runs marked `orphaned`, re-queued from the last completed tool call.
**Missed ticks** — next tick queries CMR from `last_granule_check`, not from now.

---

## PART C — THE DUAL-PROVIDER GATEWAY

| | Hackathon Azure endpoint | Groq |
|---|---|---|
| Whose quota | **shared by all fifteen teams** | **ours alone** |
| Unique capability | `gpt-audio`, `gpt-transcribe`, Azure TTS/STT, `gpt-5.5`, `grok-4.6` | high TPM headroom on `groq/compound` |

> **The shared key goes to work that needs frontier judgement or audio. Our own quota absorbs the volume.**

~90% of calls land on Groq. Fair use as an engineering decision — an autonomous agent looping on a shared key is how fifteen teams lose access at four in the morning.

| Lane | Primary | Fallback | Used by |
|---|---|---|---|
| `sanket-scout` | Groq `groq/compound` | Azure `DeepSeek-V4-Flash` | Scout |
| `sanket-classify` | Groq `openai/gpt-oss-20b` | Azure `DeepSeek-V4-Flash` | Watcher Tier 2 |
| `sanket-explain` | Groq `openai/gpt-oss-120b` | Azure `DeepSeek-V4-Pro` | Explainer, Sandbox |
| `sanket-plan` | Azure `gpt-5.5` | Groq `gpt-oss-120b` → local | Investigator |
| `sanket-critic` | Azure `grok-4.6` | Groq `qwen/qwen3-32b` | Verifier |
| `sanket-voice` | Azure `gpt-audio` | Azure TTS | Actor |
| `sanket-plan-local` | Ollama `gpt-oss-20b` | — | offline path |

```python
from litellm import Router

model_list = [
    {"model_name": "sanket-plan",
     "litellm_params": {"model": "azure/gpt-5.5",
                        "api_base": os.environ["HACKATHON_BASE"],
                        "api_key": os.environ["HACKATHON_KEY"]},
     "tpm": 30000, "rpm": 60, "order": 1},
    {"model_name": "sanket-plan",
     "litellm_params": {"model": "groq/openai/gpt-oss-120b",
                        "api_key": os.environ["GROQ_KEY"]},
     "tpm": 8000, "rpm": 30, "order": 2},
    {"model_name": "sanket-scout",
     "litellm_params": {"model": "groq/groq/compound",
                        "api_key": os.environ["GROQ_KEY"]},
     "tpm": 70000, "rpm": 30, "order": 1},
]

router = Router(
    model_list=model_list,
    routing_strategy="simple-shuffle",
    fallbacks=[
        {"sanket-plan":     ["sanket-plan-local"]},
        {"sanket-critic":   ["sanket-plan"]},
        {"sanket-classify": ["sanket-scout"]},
        {"sanket-explain":  ["sanket-classify"]},
    ],
    num_retries=3, allowed_fails=2, cooldown_time=60, timeout=45,
)
```

**Three details:** use `simple-shuffle` with tpm/rpm set, **not** `usage-based-routing-v2` — LiteLLM's own docs flag its Redis overhead as a latency problem, and `simple-shuffle` maximised throughput in their load tests · `order` gives priority inside a lane, and a 429 puts a deployment on cooldown immediately · **fallbacks cross providers in both directions**, then to local Ollama with `degraded: local` in the trace.

**Fair use:** `MAX_STEPS = 10` first · wall-clock timeout · token counter from hour one · response cache on message hash · exponential backoff with jitter · **no autonomous loop left running unattended** · keys in environment variables, never committed.

**Cost:** `agent/budget.py` tracks tokens and cost per run split by provider, converts to NPR, writes to `runs`, hard-fails to cache or Ollama rather than to a 429. The board shows cost by provider alongside the counterfactual of routing everything to `gpt-5.5`.

---

## PART D — CHANNELS

### The board

Public, always on, auto-refreshing, Nepali toggle, 2G-capable. **It does not wait for a human to look at it, because the agents already looked, decided, explained and wrote the status.**

```
┌──────────────────────────────────────────────────────────────────┐
│  BHOTEKOSHI–TRISHULI CORRIDOR              🟡 WATCH              │
│  Last checked 4 min ago · newest evidence 6 h old · conf. medium │
├──────────────────────────────────────────────────────────────────┤
│  Timure  🟡 14 min ●●○   Syapru Besi 🟡 41 min ●●○                │
│  Dhunche 🟢 1h20m ●●●    Betrawati   🟢 3h40m ●●●                 │
├──────────────────────────────────────────────────────────────────┤
│  3D CORRIDOR — BEFORE / AFTER          [GeoLibre, swipe handle]  │
├──────────────────────────────────────────────────────────────────┤
│  WHAT THE AGENT FOUND      run a41c · 6 steps · 1 recovery       │
│  Barrier lake grew 0.008 km² since 30 Aug. Rainfall 30th pctile  │
│  — rain does not explain it. ⚠ No claim issued on cause.         │
├──────────────────────────────────────────────────────────────────┤
│  WHY  change z=3.4 (+0.41) · lead 14 min (+0.33) · exp 916       │
│  (+0.19) · conf medium (−0.07). At 1.5 Mm³ → NORMAL. Flips 1.8.  │
├──────────────────────────────────────────────────────────────────┤
│  [lake area 2016→now, gaps shaded]  [rainfall percentile]        │
│  [lead-time distribution]           [agent run history]          │
├──────────────────────────────────────────────────────────────────┤
│  NATIONAL  47 basins swept 31 Aug · 1 active · 3 standing        │
│  Cost NPR 3.80 (Groq 2.10 · Azure 1.70) · degraded: none         │
└──────────────────────────────────────────────────────────────────┘
```

Routes: `/` board · `/preparedness` standing profiles, available at NORMAL · `/gate` approver · `/trace` rendered trace · `/build` progress.

**GeoLibre:** fork the public `giswqs/nepal-flash-floods` project (Vantor pre-event `10300100C86CED00` and `10500100364E8400`, post-event `B030001100CF1610`, OPERA disturbance overlay, 3D terrain, working swipe). **Credit Qiusheng Wu.** Generate `dist/sanket.geolibre.json` from Python. **Our addition: the modelled inundation polygon over the observed extent.** Three fixed camera bookmarks. Vertical exaggeration **1.6**, shown.

```python
from geolibre import Map
m = Map()
m.load_project("forked/nepal-flash-floods.geolibre.json")
m.add_cog(f"{CDN}/arrival_time_v2.5Mm3_t30min.tif", name="Arrival time", colormap="magma")
m.add_geojson(f"{CDN}/modelled_inundation.geojson", name="Modelled extent")
m.add_geojson(f"{CDN}/lake_polygons_by_year.geojson", name="Glacial lakes 2016–2026")
m.save_project("dist/sanket.geolibre.json")
```

**2G fallback:** 4 KB text page, same content, Nepali available.

### WhatsApp

**Twilio Sandbox.** Sending `join <code>` opens a **24-hour customer service window during which free-form text and media can be sent without a template.** That is the opt-in and the mechanism.

Practical: free trial accounts include 100 WhatsApp messages · sandbox sessions expire three days after joining · the sandbox number can be country-restricted, so **test delivery to a Nepali number on day one.**

**Three tiers**, slot-filled from Explainer output: resident (Nepali, settlement, time, one action, **plus the inundation map image**) · institutional (arrival times, basis, confidence, evidence age, "this is a scenario", **and what was refused**) · **approver** (the gate: attribution, counterfactual, flip point, before/after image, `Reply APPROVE <run_id>`).

Twilio inbound webhook → Flask route → match `run_id` and sender against `gates` → record identity, timestamp, decision → release queued sends. Unmatched or unauthorised replies logged and ignored. `STOP` unsubscribes and is honoured before any send.

### Voice and SMS

`gpt-audio` / Azure TTS generating real Nepali audio, ~22 s, arrival time interpolated into a template with slots. Dialler simulated and declared; audio real. SMS 140 characters, Nepali, simulated gateway, declared.

---

## PART E — REPLAY MODE

```yaml
# core/watch/bhotekoshi.replay.yml
mode: replay
replay:
  label: "REPLAY — Bhotekoshi barrier lake, 27–28 August 2026"
  source: data/replay/bhotekoshi_2026_08/
  clock_start: 2026-08-27T06:00:00Z
  clock_end:   2026-08-28T18:00:00Z
  speed: 3600
  as_of_follows_clock: true
```

**Replay the barrier lake, not the 26 August collapse.** The collapse was unpredictable and the system would not have caught it; replaying it would be dishonest theatre. The barrier lake formed on the 27th and began overflowing on the 28th — **over a day of genuine lead time on an impoundment visible from orbit.**

**Only the clock is simulated.** Granules, DEM, exposure layers and solver outputs are real, and **the agents run unmodified.**

**Honesty rules:** persistent replay banner, visually distinct · `REPLAY` marker on every trace line · `[REPLAY — TEST]` prefix on every outbound message · say it out loud before starting · the real-vs-mocked list records: data real, clock simulated, dialler simulated, WhatsApp real, contacts synthetic.

---

## PART F — THE TRACE

Deliverable 2, most closely read artefact. **Write the logger in Phase 0, before the loop.** Failed steps stay in. Rendered at `/trace`.

```
[09:12:03] TRIGGER  scheduled 15m · basin=bhotekoshi (tier: active) · run=a41c
[09:12:03] MEMORY   1 anomaly open (anom_07, first seen 30 Aug) · last run 08:57
[09:12:04] WATCH    2 new granules since 08:57 · DSWx-S1 T45RUL, DIST-ALERT
[09:12:06] WATCH    water delta +0.008 km2 vs 14-obs baseline (z=3.4)
[09:12:06] WATCH    classify [groq/gpt-oss-20b] → investigate · 240 tok
[09:12:07] STEP 1   [azure/gpt-5.5] plan: confirm growth, rule out rain,
                    size the impoundment, route it, count exposure, precedent
[09:12:08] TOOL     detect_water_change(...) → +0.008 km2, 0.041 total, conf 0.78
[09:12:10] TOOL     precip_percentile(lhende, 2026-09-02) → ERROR 504
[09:12:15] RETRY    precip_percentile(...) after 5s backoff → 30th percentile
[09:12:16] STEP 3   rain does not explain the change · continue
[09:12:17] TOOL     stage_volume(85.377,28.271) → 2.31e6 m3 at spill level
[09:12:19] TOOL     breach_hydrograph(2.5e6, 1800, partial)
[09:12:22] TOOL     route_flood(hyd_11) → arrival raster ok
[09:12:24] TOOL     exposure_at(inun_11) → Timure 14min/312 · Syapru 41min/604
[09:12:25] TOOL     precedent(bhotekoshi) → 2023-07, 2025-07-08, 2026-08-26
[09:12:27] VERIFY   [azure/grok-4.6] independence: dhm_icimod_imagery ×2 sources
[09:12:27] VERIFY   cause of 26 Aug — CONTRADICTION, evidence insufficient
[09:12:27] VERIFY   VETO claim "supraglacial lake outburst confirmed"
[09:12:28] VERIFY   confidence medium · newest evidence 6h · 0 records rejected
[09:12:29] EXPLAIN  [groq/gpt-oss-120b] attribution: z 0.41 · lead 0.33 ·
                    exposure 0.19 · confidence −0.07
[09:12:29] EXPLAIN  counterfactual: at 1.5 Mm3 → Timure 26 min, status NORMAL
[09:12:29] EXPLAIN  flip point: volume < 1.8 Mm3
[09:12:30] EXPLAIN  3 registers rendered · numeric consistency check passed
[09:12:30] ACTION   write_status(Timure, WATCH) → board updated
[09:12:30] ACTION   write_status(Syapru Besi, WATCH) → board updated
[09:12:30] MEMORY   anom_07 updated: growing, 3rd consecutive run
[09:12:31] GATE     whatsapp+voice+sms (61 contacts) → HUMAN APPROVAL REQUIRED
[09:12:31] GATE     whatsapp sent to DDMC Rasuwa duty officer · deadline 09:42
[09:19:41] APPROVED via whatsapp reply · +977-98••••••41 · "APPROVE a41c"
[09:19:42] ACTION   whatsapp ×61 · ne-NP · map attached · 58 delivered
[09:19:42] ACTION   voice_call ×61 · ne-NP · 54 connected · 7 queued
[09:19:43] ACTION   send_sms ×61 · 138 chars · ne-NP
[09:19:58] DONE     8 steps · 1 failure recovered · 1 veto · 1 gate held
                    azure 6,140 tok · groq 5,262 tok · NPR 3.80 · degraded: none
```

---

## PART G — DATA

### Must-have (8)

| # | Dataset | Access | Role |
|---|---|---|---|
| 1 | **NASA HMA 8 m DEM**, tiles 642/643/675/676 | NSIDC, Earthdata login | Stage–volume, routing, 3D terrain. **No fallback — register first.** |
| 2 | **OPERA DSWx-S1** | `earthaccess` + CMR | All-weather water/blockage detection. **The trigger.** |
| 3 | **OPERA DIST-ALERT-HLS v1** | `earthaccess` + CMR | Disturbance, NRT. **Use v1** — v0 decommissioned Apr 2025. |
| 4 | **Sentinel-2 L2A** | Planetary Computer STAC, anonymous | Lake area series |
| 5 | **Sentinel-1 GRD** | Planetary Computer, anonymous | Radar cross-check. ⚠️ `sentinel-1-rtc` needs a key — use GRD or OPERA RTC-S1 |
| 6 | **HDX `hot_flood_npl`** + `hot_flood_npl_buildings_damage` | HDX API, daily | Observed extent, damage |
| 7 | **OSM / HOT exposure** | HDX + HOT Raw Data API, **ODbL** | Everything counted; routing network |
| 8 | **IMERG or CHIRPS** | NASA GES DISC / UCSB CHC | The rule-out evidence |

### High value

**ICIMOD glacial lake + PDGL inventory** (47 PDGLs, DOI 10.26066/RDS.1971946 / 1971950) — **Scout's population** · **HMAGLOFDB** (697 GLOFs 1833–2022) · **Copernicus EMS EMSR927** (validation: Syapru Besi AOI >240 destroyed, 32 damaged, WorldView-3 27/08 05:05 UTC) · **UNOSAT** mudflow extent · **Microsoft AI for Good** damage via HDX (`independence_group: cv_damage_vhr`) · **WorldPop** CC BY 4.0 · **Vantor Open Data** WorldView pre/post, no-sign-request S3, **CC BY-NC 4.0** · **Planet Crisis Response**, CC BY-NC 4.0 · **Copernicus DEM GLO-30** (Scout's national screening) · **OCHA COD-AB** ADM2 CC BY-IGO.

### Manual downloads

**Needs credentials:** NASA Earthdata (gates HMA DEM, all OPERA, IMERG) · hackathon API key · **Groq API key** · **Twilio account SID and auth token**.
**User fetches manually:** ICIMOD RDS inventories · Copernicus EMS EMSR927 · UNOSAT extent · Microsoft AI for Good damage layer.

### Synthetic — declare it

Institutional contact lists matching the real distribution (DDMC duty officer, DHM divisional hydrologist, local administration, hydropower operator, police post, health post, school, community focal point), non-routable numbers. **The voice audio and WhatsApp messages are real.**

### Excluded

Any paid API · Google Earth Engine as a runtime dependency · Google Photorealistic 3D Tiles · any real personal data.

### Open contribution (+3)

`sanket-mcp` — the twelve tool schemas over MCP, published with a README. The corridor lakehouse — silver layers plus the provenance registry — to HuggingFace Datasets with a per-layer licence table. Both linked in the README.

**Licence stack:** most restrictive term wins per derived layer. NC-derived products in a separate directory.

---

## PART H — ENGINEERING STANDARDS

**No comments. None.** No inline, no block, no `# TODO`, no commented-out code, no section banners. If code needs explanation, the names are wrong or the function is too big.

Type hints on every Python signature; `mypy --strict` on `core/` and `analysis/`. TypeScript strict, no `any`. Functions under 40 lines, files under 400. Pure functions where possible, I/O at the edges. One responsibility per module. Dependency direction one-way: `board → api → agent → analysis → core`, enforced by import-linter. Pydantic at every boundary. Typed exceptions from `core/errors.py`, never bare `except`. `structlog`, never `print`. Config in `config.py` and `.env`. README per package — **that is where explanation lives.** `ruff` + `black` + `mypy` + `pytest` + import-linter in CI and pre-commit.

**On agent frameworks:** hand-rolled loop by default. A two-hundred-line loop you fully understand is worth more under questioning than a framework you cannot explain. `smolagents` is used in exactly one place (the sandbox). **CrewAI is out.**

---

## PART I — REPO LAYOUT

```
sanket/
├─ PLAN.md · PROGRESS.md · progress.json · MANUAL_DOWNLOADS.md · README.md
├─ core/
│  ├─ config.py  errors.py  provenance.py
│  ├─ registry/*.yml        provenance contracts, one per layer
│  ├─ watch/*.yml           corridor definitions incl. bhotekoshi.replay.yml
│  ├─ lakehouse.py          DuckDB + as_of firewall + rejection log
│  ├─ connectors/           cmr opera stac hdx icimod hmaglofdb dhm worldpop usgs
│  └─ publish.py
├─ analysis/
│  ├─ eo/       masks dswx dist mndwi baselines changedetect national_sweep
│  ├─ hydro/    dem xsections stage_volume breach route1d swe2d_torch scenarios
│  └─ exposure/ cells leadtime isolation preparedness assembly
├─ agent/
│  ├─ router.py             LiteLLM Router — ONLY place a provider is named
│  ├─ budget.py cache.py trace.py
│  ├─ scout.py watcher.py loop.py verifier.py explainer.py sandbox.py
│  ├─ tools/  schemas.py ledger.py
│  └─ rag/    store.py ingest.py retrieve.py guard.py
├─ watch/      daemon.py scheduler.py triggers.py tiers.py queue.py state.py replay.py
├─ actions/    board.py gate.py voice.py sms.py whatsapp.py inbound.py
│              scripts_ne.py templates_wa.py
├─ api/        app.py (Flask) routes/ sse.py
├─ mcp/        server.py README.md
├─ board/      Next.js — board, preparedness, gate, trace, build
├─ notebooks/  00_env 01_inventory 02_dem 03_eo 04_precip 05_exposure
│              06_calibration 07_validation
├─ data/       bronze/ silver/ gold/ manifests/ replay/bhotekoshi_2026_08/
├─ dist/       sanket.geolibre.json · COGs · PMTiles · chroma/
├─ forked/     nepal-flash-floods.geolibre.json · vendored geo-pera solvers
└─ tests/
```

**Runtime:** Python 3.11 · Flask 3 + gunicorn/gevent · APScheduler · **litellm** · **smolagents** · **twilio** · **mcp** · Pydantic 2 · structlog · DuckDB(spatial, httpfs) · SQLite · rasterio · rioxarray · xarray · geopandas · shapely · pysheds · whitebox · pystac-client · odc-stac · earthaccess · torch · rio-cogeo · rio-rgbify · titiler · omnicloudmask · omniwatermask · chromadb · sentence-transformers.

**Board:** Next.js 15 App Router · TypeScript strict · maplibre-gl · deck.gl · recharts · zustand · tailwindcss · GeoLibre embedded.

---

## PART J — THE FIFTEEN PHASES

### PHASE 0 — Scaffold, both providers, router, logger, walking skeleton

**Build**
- Repo structure as above, README per package; `pyproject.toml` pinned; ruff, black, mypy --strict, pytest, import-linter, pre-commit, CI
- **`curl` check against BOTH providers on every machine.** Record working model lists in `PROGRESS.md`.
- **`agent/router.py`** — LiteLLM Router, all seven lanes, cross-provider fallbacks, tpm/rpm, `simple-shuffle`, cooldowns, retries. **The only place a provider is named.**
- `agent/budget.py` — tokens and cost per run, split by provider, in NPR
- **`agent/trace.py` — the logger. Before the loop.** Timestamp, agent, step, tool, args, result, provider, tokens, cost.
- `core/config.py`, `core/errors.py`, `core/provenance.py`
- **Walking skeleton:** a scheduled tick → one real tool (`stage_volume` on the real DEM) → `write_status` → a board page changes. Ugly, narrow, real, end to end.
- Flask `/api/health`, `/api/status`, `/api/progress`; Next.js board shell and `/build`
- `PROGRESS.md`, `progress.json` with all fifteen phases
- Decide GeoLibre embed-vs-plugin; record the reasoning

**Exit criteria** — `pytest`, `mypy --strict`, `ruff` clean; zero comments in any source file · **both providers reachable, both model lists recorded** · **a lint rule fails the build if any file other than `router.py` imports a provider SDK** · the skeleton runs on a timer with nobody pressing anything and the board visibly changes · the trace contains a real run with provider and cost attribution

### PHASE 1 — Data acquisition and EDA

**The longest phase. Do not compress it.** AOI approximately `[85.10, 27.80, 85.45, 28.55]`; record the final bbox in the corridor YAML.

Connectors returning provenance-stamped bronze artifacts with fetch manifests; checksum-skip; bronze→silver reprojection to EPSG:32645 as GeoParquet/COG; notebooks 01–05.

**Exit criteria** — every Tier-1 dataset in `bronze/` with a manifest or listed pending with a working link · all promoted to `silver/` · notebooks 01–05 execute top to bottom, outputs committed · **cloud-fraction distribution documented** — this decides how much optical is usable at all · data-quality summary in `PROGRESS.md`

### PHASE 2 — Lakehouse, provenance, corridor registry

`core/registry/*.yml` with the full contract schema including `cannot_tell_you` and `independence_group`, Pydantic-validated at import · `core/watch/*.yml` · `core/lakehouse.py` with `query(sql, *, as_of)` filtering **and counting** post-cutoff rows · gold builders · `core/publish.py`.

**Enforce in code:** admin boundaries are display and filter only; scoring functions never receive admin geometry. Test it.

**Exit criteria** — every silver layer has a validated contract · `as_of` filtering excludes post-cutoff rows with a non-zero rejection count · **a second corridor YAML loads without a code change** · publish produces a valid dataset directory

### PHASE 3 — Terrain and hydraulics

DEM conditioning · `xsections.py` · `stage_volume.py` · `breach.py` · `route1d.py` and `swe2d_torch.py` **vendored from `geo-pera/bhotekoshi-2026-reconstruction` (MIT)**, licence headers retained · `scenarios.py` **precomputing the full grid** (0.5–5.0 Mm³ × 5 min–6 h) as COGs · notebook 06 calibrating against observed flow heights (geo-pera reports median ~70 m through the confined gorges, bank measurements 40–134 m at Rasuwagadhi) with **residuals plotted**.

Every output `claim_type: scenario`. Record that the **DEM predates the event.**

**Exit criteria** — channel network matches the real river · stage–volume curve for the barrier lake location · scenario grid as COGs loading under 200 ms · calibration residuals with a stated error range · `route1d` under 10 s on CPU

### PHASE 4 — EO detection and baselines

`masks.py` · `dswx.py` · `dist.py` · `mndwi.py` (`independence_group: sanket_optical`) · **`baselines.py` — rolling 14-observation statistics per product per tile with variance** · `changedetect.py` (z-score) · `lake_series.py` with cloud-gap logging · agreement raster.

No custom training. No YOLO.

**Exit criteria** — lake area series 2016→now · Purepu detected in the 2023/2024/2025 windows or a documented explanation · baselines stored with variance · cloud-gap log

### PHASE 5 — Exposure, lead times, preparedness

`cells.py` · `leadtime.py` (histogram + ECDF) · `isolation.py` · **`preparedness.py`** producing the standing profile per settlement across the full scenario range · **`assembly.py`** for safe-point candidates and routes · notebook 07 **validating against Copernicus EMS EMSR927 and UNOSAT** with confusion matrix, IoU, precision, recall — reported whatever the numbers are.

Every count reports its dataset vintage. Population is modelled usual residence and cannot show post-26-August displacement — state this in the output.

**Exit criteria** — lead times per settlement per scenario · histogram shows non-trivial population under 30 minutes · **a standing preparedness profile exists for every settlement with no event and no alert** · validation notebook produces real metrics with stated caveats

### PHASE 6 — The daemon

`watch/daemon.py`, `scheduler.py`, `queue.py`, `state.py` · full state schema · `triggers.py` · `tiers.py` · hysteresis, cooldown, fingerprinting · cold start and `warming_up` · crash recovery · missed-tick handling.

**Exit criteria** — `sanket watch start` runs unattended with **no human input path** · a new granule triggers Tier 1 with nobody pressing anything · **Tiers 0 and 1 make zero LLM calls, asserted in a test** · killing and restarting recovers the queue · **the second run on the same anomaly behaves differently from the first**

### PHASE 7 — Scout

`agent/scout.py` · `analysis/eo/national_sweep.py` · `basin_tiers` table · weekly scheduler job · standing exposure ranking across all 47.

**Exit criteria** — all 47 PDGLs swept in a single run, on Groq, with cost recorded · basin tiers written with drivers explaining each assignment · **promoting a corridor demonstrably changes its tick cadence** · the board's national panel shows sweep date and tier counts

### PHASE 8 — Investigator and Verifier

`agent/loop.py` · all twelve tools with Pydantic `args_schema` and provenance envelopes · `agent/verifier.py` with the four checks and the veto, **rejecting any claim not already in the ledger** · `agent/ledger.py` · `agent/rag/` (ChromaDB, two collections, `BAAI/bge-m3`, **`published_ts` as integer epoch**, injection filtering, geopera retraction indexed as `claim_type: retracted`) · Flask SSE with `X-Accel-Buffering: no` and gevent workers.

**Exit criteria** — full investigation end to end from a real trigger · **two traces showing genuinely different tool sequences for different anomaly types** · Verifier produces `insufficient — no claim issued` on the contested 26 August attribution · a test proves the Verifier cannot introduce a claim not already in the ledger · SSE streams incrementally · one investigation under 60 seconds warm

### PHASE 9 — Explainer and the sandbox

`agent/explainer.py` — attribution decomposing the **actual** decision function, counterfactuals from the precomputed grid, flip points, what-would-change-my-mind, three registers · `agent/sandbox.py` — smolagents `CodeAgent`, read-only, gate screen only, no network, no writes, 10-second timeout.

**Exit criteria** — attribution numbers match a direct computation of the decision function, verified by test · counterfactuals match a direct grid lookup · **a test compares numeric claims across all three registers and fails on divergence** · a test proves no fact appears in any rendering that is not in the ledger · if the Verifier vetoed, all three registers say so · a follow-up question with no tool returns a correct answer with the Python shown · **a test proves the sandbox cannot write status, trigger a notification or alter a gate decision** · deleting `sandbox.py` leaves every other test green

### PHASE 10 — Actions, the gate, and WhatsApp

`actions/board.py` · `actions/gate.py` · `actions/scripts_ne.py` · `actions/voice.py` · `actions/sms.py` · **`actions/whatsapp.py`** (Twilio send with media attachment, delivery status callback) · **`actions/inbound.py`** (webhook handling `APPROVE <run_id>`, `REJECT <run_id>`, `STOP`; match sender against `gates`; log and ignore anything unauthorised) · `actions/templates_wa.py` (three tiers, Nepali and English, slot-filled) · `subscribers` table.

**Exit criteria** — WATCH writes autonomously and the board changes · ALERT stops at the gate with no outbound action · **a real WhatsApp message with an attached map image arrives on a real phone** · **replying `APPROVE <run_id>` from the registered approver's number releases the sends; replying from any other number does not** · `STOP` unsubscribes and is honoured before the next send · cooldown blocks a second message inside the window · delivery status written back to `notifications` · real Nepali audio plays

### PHASE 11 — Replay mode

`watch/replay.py` · `data/replay/bhotekoshi_2026_08/` with manifest and checksums · `core/watch/bhotekoshi.replay.yml` · replay banner · `REPLAY` marker on every trace line · `[REPLAY — TEST]` prefix on every outbound message.

**Exit criteria** — the full chain runs end to end from replay with **no human input beyond starting it** · **running it three times produces at least two different tool sequences** (if identical every time, the Investigator is over-constrained — loosen the prompt) · the board is unambiguously marked as replay · every outbound message carries the prefix · replay manifest checksums verify against the real granules

### PHASE 12 — The board

Status header · settlement tiles · "what the agent found" · **the WHY panel** · four charts · **national panel** · cost per run split by provider · GeoLibre embed with the Vantor swipe, our modelled inundation overlay and three camera bookmarks · **`/preparedness`** standing profiles available at NORMAL · `/gate` with Explainer's pack and the Ask panel · **`/trace`** rendered, colour-coded by agent, failures in red with retries indented · `/build` · **Nepali toggle** · **4 KB text fallback** · auto-poll with last-checked and evidence-age always visible.

**Exit criteria** — board updates within seconds of a status write with no human action · GeoLibre embed loads with the working swipe and our overlay · Nepali toggle works across charts, tiles and the WHY panel · **the 4 KB fallback renders under a throttled connection, demoed live** · `/trace` renders a complete run legibly with the failure and recovery visible · every displayed number carries its source and vintage

### PHASE 13 — Resilience and provider failover

Full degradation ladder: Azure → Groq → local Ollama → deterministic mode → last known good, **each step stamped in the trace** · offline verification with the network physically disconnected · **provider failover verified by revoking one key at runtime.**

**Exit criteria** — revoking the Azure key mid-run: the investigation completes on Groq and the trace records the switch · revoking both: deterministic mode still updates the board · network disconnected: last known good served with age in hours

### PHASE 14 — Validation and deliverables

Complete notebooks 06 and 07; publish confusion matrix, IoU, precision and recall against EMSR927; plot calibration residuals; write an honest reading of where and why the model fails.

`mcp/server.py` exposing the twelve tool schemas; publish as `sanket-mcp`. `core/publish.py` executed → HuggingFace dataset with per-layer licence table.

Clean trace capture, **failed steps retained** · one-page Solution Sheet (one sentence · named user · what the agent does unasked · architecture diagram · tools and models · human checkpoint · Bad Day paragraph · **blunt real-vs-mocked list**) · README with **"Brought in"** listing GeoLibre, geo-pera solvers, HMAGLOFDB, LiteLLM, smolagents and every library · the 60-second video.

**Exit criteria** — real validation numbers published with caveats · an external MCP client can call `stage_volume` and `exposure_at` against the published server and get correct results · full demo runs six times without failure · trace legible and unsanitised · Solution Sheet complete · README "Brought in" complete · open contribution links live

---

## PART K — RULES YOU MUST NOT BREAK

1. **No comments in code.**
2. **Never skip or stub a phase.** If genuinely infeasible, stop, write it in `PROGRESS.md`, and ask.
3. **No human input path to start a run.** Signal 05 is the whole point.
4. **`MAX_STEPS = 10`.** Shipped before anything else.
5. **Never leave an autonomous loop running unattended.**
6. **The LLM never computes a number.** Deterministic Python tools only.
7. **Never hardcode the tool sequence.** Different anomalies must produce different paths.
8. **`scenario` never renders like `observation`.**
9. **Never claim prediction.** Not in code, not on the board, not in a log line.
10. **The gate holds.** No outbound action without recorded approval from the registered approver.
11. **Declare everything mocked or synthetic** — contacts, dialler, precomputed scenarios, replay clock — on the Solution Sheet and on stage. A hardcoded output presented as a live run is disqualifying.
12. **Keys in environment variables, never in a commit.**
13. **Update `PROGRESS.md` and `progress.json`** at every phase boundary.
14. **Ask before inventing.** Verify any dataset, repo or API not named here.
15. **Cite every number with its date.** Casualty figures are provisional.
16. **The Explainer may not introduce a fact absent from the ledger**, may not omit a veto, and generates voice and SMS scripts from templates with slots — never free composition.
17. **Every LLM call goes through `agent/router.py`.** No direct provider client anywhere else. Enforced by a lint rule that fails the build.
18. **The sandbox is read-only and advisory.** It may never write status, trigger a notification, or influence a gate decision. Enforced by test.
19. **In replay mode** every outbound message is prefixed `[REPLAY — TEST]` and every trace line carries a `REPLAY` marker. No exceptions.
20. **No recipient is contacted without a recorded opt-in.** `STOP` is honoured before any send.
21. **Replay simulates the clock only.** Granules, DEM, exposure layers and solver outputs are real, and the agents run unmodified.

---

## START NOW

Produce `PLAN.md`, `MANUAL_DOWNLOADS.md`, `PROGRESS.md`, `progress.json`, your assumptions and your open questions.

Then stop and wait for approval before Phase 0.
