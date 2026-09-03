# 02 — SANKET Technical Specification

Engineering · Architecture, autonomy, agents, gateway, models, datasets, channels, replay, limitations

---

## 1. Architecture

```
                     TRIGGERS — no human input path exists
  ┌──────────────────────────────────────────────────────────────────┐
  │ APScheduler tick (per basin tier) · new OPERA granule (NASA CMR) │
  │ · DHM stage threshold · weekly national sweep · replay clock     │
  └──────────────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
  ┌───────────┐  weekly                ┌───────────┐
  │  SCOUT    │──► [ basin_tiers ]────►│  WATCHER  │  Tier 0/1 pure Python
  │  Groq     │     sets cadence       │  Groq     │  Tier 2 one small call
  └───────────┘                        └───────────┘
                                             │ InvestigationJob
                                             ▼
                                   [ SQLite work queue ]  ← survives crash
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  INVESTIGATOR    │  12 tools
                                   │  Azure gpt-5.5   │  MAX_STEPS=10
                                   └──────────────────┘
                                             │ EvidenceLedger
                                             ▼
                                   ┌──────────────────┐
                                   │  VERIFIER        │  independence, licensing
                                   │  Azure grok-4.6  │  contradiction, VETO
                                   └──────────────────┘
                                             │ VerificationTable + StatusDecision
                                             ▼
                                   ┌──────────────────┐
                                   │  EXPLAINER       │  attribution, counterfactual
                                   │  Groq gpt-oss-120b│ flip point, 3 registers
                                   └──────────────────┘
                                             │ PublicNote · EvidencePack · Scripts
                                             ▼
                                   ┌──────────────────┐
                                   │  ACTOR           │
                                   └──────────────────┘
                          ┌──────────────────┴──────────────────┐
                   AUTONOMOUS (WATCH)                    GATED (ALERT)
                   board write, run record,              → WhatsApp to duty officer
                   DHM duty channel                      → reply APPROVE <run_id>
                          │                                      │
                          ▼                                      ▼
                  ┌───────────────┐              voice (Nepali) · SMS · WhatsApp
                  │ PUBLIC BOARD  │                    + inundation map image
                  │ Next.js       │
                  │ GeoLibre 3D   │
                  │ Nepali · 2G   │
                  └───────────────┘

  STATE  SQLite: basin_tiers · baselines · anomalies · runs · notifications
                 · gates · subscribers
  DATA   DuckDB(spatial, httpfs) · GeoParquet · COG · PMTiles · registry/*.yml
  TRACE  append-only, all six agents, rendered at /trace
```

Dependency direction one-way: `board → api → agent → analysis → core`. Enforced by import-linter in CI.

---

## 2. The autonomy engine

### 2.1 Daemon

```
watch/
  daemon.py      process entry, signal handling, graceful shutdown
  scheduler.py   APScheduler, interval per basin tier, staggered
  triggers.py    CMR granule poll · DHM stage · anomaly re-check due
  tiers.py       Tier 0 tick · Tier 1 change detection · Tier 2 classification
  queue.py       SQLite-backed work queue
  state.py       all state tables
  replay.py      replay clock, timed granule release, as_of advance
```

### 2.2 Four tiers

| Tier | Fires | Cost | Does |
|---|---|---|---|
| **0** | per basin tier (15 min / 6 h / weekly) | **zero LLM** | CMR `updated_since` poll, DHM stage, anomaly re-check due |
| **1** | new granule | **zero LLM** | Water and disturbance delta vs a rolling 14-observation baseline, as a z-score against that baseline's own variance |
| **2** | change outside band | one small call | `investigate \| artefact \| seasonal \| insufficient_data` |
| **3** | `investigate` | the agent | Investigator loop |

Tiers 0 and 1 make **zero LLM calls** — asserted in a test.

Tier 2 exists because radar layover in a steep valley, wet-snow backscatter drops and orbit-geometry differences all look like change and are not.

### 2.3 Triggers

**Schedule.** APScheduler, cadence read from `basin_tiers`, staggered across basins. Overnight the interval widens.

**New granule.** OPERA products publish through NASA CMR, which supports a temporal `updated_since` query. Store `last_granule_check` per basin per product and query forward from it. **The system reacts to publication, not to orbit prediction.** Sentinel-1 revisit over Nepal is ~6–12 days; OPERA processing latency adds hours to days. Both logged with every finding.

**Stage threshold.** Deliberately weakest. A downstream gauge reports a flood already in progress — by the time Betrawati's stage moves, Timure has been hit. Confirmation channel, not early warning.

**Weekly sweep.** Scout, across all 47 PDGLs.

**Replay clock.** In replay mode only; releases stored granules on an accelerated clock with `as_of` advancing.

### 2.4 State schema

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

### 2.5 Behavioural guarantees

**Hysteresis** — escalation threshold above the maintenance threshold; de-escalation below it. Status does not flap.
**Cooldown** — enforced in `notifications` **before** the gate, not after. No re-contact inside the window unless the level increases.
**Fingerprinting** — `hash(location_cell, feature_id, change_signature)`. One event across three granules is one anomaly with three observations.
**Cold start** — backfill ~24 months of archive; corridor marked `warming_up` until variance is estimable; the board says why.
**Crash recovery** — SQLite queue; interrupted runs marked `orphaned` and re-queued from the last completed tool call. State never lives only in memory.
**Missed ticks** — next tick queries CMR from `last_granule_check`, not from now. The gap shows in run history.

---

## 3. The six agents

Full detail in `04-AGENT-REFERENCE.md`. Summary:

| Agent | Provider · model | Fires | Job | Communicates via |
|---|---|---|---|---|
| **Scout** | Groq `groq/compound` | weekly | Sweep 47 PDGLs, assign watch tiers | `basin_tiers` |
| **Watcher** | Groq `gpt-oss-20b` (T2 only) | tick + granule | Decide whether to investigate | work queue |
| **Investigator** | Azure `gpt-5.5` | on `investigate` | Goal + 12 tools, chooses its own path | `EvidenceLedger` |
| **Verifier** | Azure `grok-4.6` | after Investigator | Adjudicate, assign confidence, veto | `VerificationTable` + `StatusDecision` |
| **Explainer** | Groq `gpt-oss-120b` | after Verifier | Attribution, counterfactuals, flip point, 3 registers | `PublicNote` · `EvidencePack` · `VoiceScript` |
| **Actor** | deterministic + Azure `gpt-audio` | after Explainer | Board, gate, voice, SMS, WhatsApp | DB writes, Twilio |

**Agents do not talk to each other. They hand typed artifacts through shared state.** No agent calls backwards.

### 3.1 The loop

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

**Never hardcode the tool sequence.** A fixed pipeline with an LLM filling in text is automation, not agency.

### 3.2 The twelve tools

| Tool | Datasets behind it |
|---|---|
| `search_granules(product, bbox, since)` | NASA CMR |
| `detect_water_change(granule, baseline)` | OPERA DSWx-S1 + `baselines` |
| `detect_disturbance(granule)` | OPERA DIST-ALERT-HLS v1 |
| `lake_area_series(catchment, from, to)` | Sentinel-2 L2A, OmniCloudMask, OmniWaterMask, MNDWI+Otsu |
| `precip_percentile(basin, date)` | GPM IMERG / CHIRPS vs 20-year climatology |
| `stage_volume(point)` | NASA HMA 8 m DEM |
| `breach_hydrograph(volume, duration, mode)` | derived |
| `route_flood(hydrograph)` | HMA 8 m DEM + precomputed scenario grid |
| `exposure_at(inundation)` | OSM/HOT, WorldPop, HDX `hot_flood_npl` |
| `precedent(basin)` | HMAGLOFDB, ICIMOD PDGL, BIPAD |
| `science_lookup(query)` | ChromaDB `science` |
| `write_status(settlement, level, evidence)` | **autonomous consequence** |

Gated — may be requested, not executed: `voice_call`, `send_sms`, `send_whatsapp`.

**The LLM never computes a number.** Every quantity comes from a deterministic Python function.

### 3.3 Evidence envelope

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

`claim_type` ∈ `{observation, correlation, model_output, scenario, hypothesis, recommendation}`. **The renderer refuses to display a `scenario` in the same visual style as an `observation`.**

### 3.4 Claim and veto

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

**Enforced in code, not the prompt:** reject any `Claim` whose `statement` was not already in the ledger.

### 3.5 The Analyst Sandbox

`smolagents` `CodeAgent` with `geopandas`, `rasterio` and a **read-only** DuckDB connection to the gold layer. Surfaced only as an Ask panel on the gate screen, for approver follow-ups no tool covers.

Guardrails: read-only · no network · no filesystem writes · 10-second timeout · results tagged `claim_type: model_output` · **cannot write status, trigger a notification, or influence a gate decision.** Deleting it leaves every other test green.

---

## 4. The dual-provider gateway

### 4.1 Allocation principle

| | Hackathon Azure endpoint | Groq |
|---|---|---|
| Whose quota | **shared by all fifteen teams** | **ours alone** |
| Unique capability | `gpt-audio`, `gpt-transcribe`, Azure TTS/STT, `gpt-5.5`, `grok-4.6` | high token-per-minute headroom on `groq/compound` |

> **The shared key goes to work that needs frontier judgement or audio. Our own quota absorbs the volume.**

~90% of calls land on Groq. This is fair use as an engineering decision — an autonomous agent looping on a shared key is exactly how fifteen teams lose access at four in the morning.

| Lane | Primary | Fallback | Used by |
|---|---|---|---|
| `sanket-scout` | Groq `groq/compound` | Azure `DeepSeek-V4-Flash` | Scout |
| `sanket-classify` | Groq `openai/gpt-oss-20b` | Azure `DeepSeek-V4-Flash` | Watcher Tier 2 |
| `sanket-explain` | Groq `openai/gpt-oss-120b` | Azure `DeepSeek-V4-Pro` | Explainer, Sandbox |
| `sanket-plan` | Azure `gpt-5.5` | Groq `gpt-oss-120b` → local | Investigator |
| `sanket-critic` | Azure `grok-4.6` | Groq `qwen/qwen3-32b` | Verifier |
| `sanket-voice` | Azure `gpt-audio` | Azure TTS | Actor |
| `sanket-plan-local` | Ollama `gpt-oss-20b` | — | offline path |

### 4.2 LiteLLM Router

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

**Three details that matter:**

1. **`simple-shuffle`, not `usage-based-routing-v2`.** LiteLLM's own docs flag usage-based routing as a poor production choice — Redis operations on every request add real latency. With `tpm`/`rpm` set per deployment, `simple-shuffle` does a weighted pick and maximised throughput in their load tests. Single instance, no Redis: unambiguously right.
2. **`order` gives priority inside a lane.** On a 429 the failing deployment goes on cooldown immediately and the router shifts provider without waiting for the fallback chain.
3. **Fallbacks cross providers both directions.** Azure rate-limited → planning drops to Groq. Groq quota exhausted → Scout and Classify drop to Azure. Both gone → local Ollama, trace records `degraded: local`.

**`agent/router.py` is the only place in the codebase where a provider is named.** Enforced by a lint rule that fails the build.

### 4.3 Fair use and cost

`MAX_STEPS = 10` shipped first · wall-clock timeout per run · token counter from hour one · response cache keyed on message hash · exponential backoff with jitter · **no autonomous loop left running unattended** · keys in environment variables, never committed.

`agent/budget.py` tracks tokens and cost per run **split by provider**, converts to NPR, writes to `runs`, and hard-fails to cache or Ollama rather than to a 429. The board shows cost per run by provider alongside the counterfactual of routing everything to `gpt-5.5`.

---

## 5. Models

### 5.1 Language

Covered in §4. Embeddings: **`BAAI/bge-m3` locally** via `sentence-transformers` — multilingual, handles Nepali source text, consumes no API quota.

### 5.2 Earth observation

| Component | Role | Decision |
|---|---|---|
| **OPERA DSWx-S1** (NASA/JPL) | All-weather surface water, 30 m, every few days | **Use.** A pre-computed product, and the primary trigger source. |
| **OPERA DIST-ALERT-HLS v1** | Land-surface disturbance, 30 m, every 2–4 days, NRT | **Use v1.** V0 provisional decommissioned April 2025. |
| **OmniCloudMask / OmniWaterMask** | Per-scene cloud and water masking | **Use.** `pip`-installable, from the geo-pera pipeline. |
| **MNDWI + Otsu** | Our own optical water detector | **Build.** Its value is *independence* from OPERA. `independence_group: sanket_optical`. |
| Prithvi-EO-2.0-Sen1Floods11 | Third opinion | **Optional.** ~446 lowland training chips, effectively no Himalayan signal. Caveat if used. |
| YOLO · SegFormer · Clay · SatMAE · SAM 2 · custom training | — | **No.** Wrong task shape, no Himalayan validation set, four events is not a validation set. |

**Baselines are computed by the system** — rolling 14 observations per product per tile, with variance. "Abnormal" is measured, not hardcoded.

**Agreement raster:** per-pixel n-of-3 concordance across independent detectors, feeding both the Verifier's independence check and the board's confidence colouring.

### 5.3 Hydraulics

```
NASA HMA 8 m DEM (void-filled, datum-corrected, mosaicked)
  ├─ pysheds / WhiteboxTools → fill → flow dir → flow accum → channel → HAND
  ├─ xsections.py         → cross-sections along the reach
  ├─ stage_volume.py      → hypsometric curve at any blockage point
  └─ breach.py            → hydrograph {partial, full, progressive}
        ├─ swe2d_torch.py ⭐ PRIMARY — 2D shallow water, PyTorch, CUDA/MPS/CPU
        ├─ route1d.py        CPU, seconds, always-works fallback
        └─ r.avaflow         offline precompute only, one still for credibility
             └─ arrival-time raster · peak-depth raster · inundation polygon
```

`swe2d_torch.py` and `route1d.py` **vendored from `geo-pera/bhotekoshi-2026-reconstruction` (MIT)**, licence headers retained.

**Scenario grid precomputed:** volume 0.5–5.0 Mm³ × breach 5 min–6 h, as COGs. **Declare the precompute** — it is caching, and it must be stated.

**Calibration:** tune friction and volume until the model reproduces observed flow heights measured from imagery (geo-pera reports median ~70 m through the confined gorges, bank measurements 40–134 m at Rasuwagadhi), then plot residuals.

**In provenance on every routing output:** the DEM predates the event, so post-event routing is wrong in ways we cannot correct without new survey.

### 5.4 Statistics

Rainfall anomaly = seasonal decomposition + percentile rank against a 20-year climatology. No LSTM — with four events, a deep time-series model would take a day and prove nothing.

---

## 6. Data layer

### 6.1 Provenance contract

```yaml
id: hot_fair_damage
source_org: Humanitarian OpenStreetMap Team
access: {kind: hdx, dataset: hot_flood_npl_buildings_damage, refresh: daily, checksum: sha256}
license: ODbL-1.0
spatial:  {crs: EPSG:4326, extent: [85.10, 27.80, 85.45, 28.30], resolution: building}
temporal: {observed: 2026-08-27, published: 2026-08-29}
claim_type: model_output
confidence_tier: low
good_for: [locating concentrations of probable structural damage]
cannot_tell_you:
  - severity, occupancy, or casualties (binary flag only)
  - anything under cloud, tree canopy or debris
  - buildings absent from the footprint layer never enter any score
independence_group: cv_damage_vhr
```

`independence_group` is the field nobody else models: two damage layers produced by computer vision over the same post-event imagery are **one** line of evidence, not two.

### 6.2 Corridor registry

```yaml
# core/watch/bhotekoshi.yml
basin_id: bhotekoshi_trishuli
province: Bagmati
districts: [Rasuwa, Nuwakot, Dhading]
source_catchment: {bbox: [85.30, 28.20, 85.45, 28.40], country: CN}
watched_features:
  - {id: purepu_glacier, type: supraglacial_lake, pdgl: false}
  - {id: lhende_barrier, type: barrier_lake, first_seen: 2026-08-27}
downstream_reach: [Timure, Syapru Besi, Dhunche, Betrawati, Trishuli Bazaar]
dem: hma_8m_tiles_642_643_675_676
watched_products: [OPERA_L3_DSWX-S1_V1, OPERA_L3_DIST-ALERT-HLS_V1]
authority: {level: district, body: DDMC Rasuwa}
```

Cadence is read from `basin_tiers`, not from this file. **Adding a corridor is a data operation** — tested by loading a second YAML with no code change.

### 6.3 Temporal firewall

Every data access — SQL, STAC, CMR and RAG — takes a required `as_of: date`. Records published after it are rejected **and counted**; the count is exposed and rendered. In ChromaDB, `published_ts` is an **integer epoch** — Chroma's `$lte` on strings is lexicographic and silently breaks the firewall on mixed formats.

**Hard rule:** admin boundaries are display and filter only. Scoring functions never receive admin geometry. Enforced by test. A boundary is an administrative fact, not a physical one, and this hazard's source is in another country.

### 6.4 Datasets — must-have (8)

| # | Dataset | Access | Role |
|---|---|---|---|
| 1 | **NASA HMA 8 m DEM**, tiles 642/643/675/676 | NSIDC, Earthdata login | Stage–volume, routing, 3D terrain. **No fallback — register first.** |
| 2 | **OPERA DSWx-S1** | `earthaccess` + CMR | All-weather water/blockage detection. **The trigger.** |
| 3 | **OPERA DIST-ALERT-HLS v1** | `earthaccess` + CMR | Disturbance, NRT. Use **v1**. |
| 4 | **Sentinel-2 L2A** | Planetary Computer STAC, anonymous | Lake area series |
| 5 | **Sentinel-1 GRD** | Planetary Computer, anonymous | Radar cross-check. ⚠️ `sentinel-1-rtc` needs a key — use GRD or OPERA RTC-S1 |
| 6 | **HDX `hot_flood_npl`** + `hot_flood_npl_buildings_damage` | HDX API, daily | Observed extent, damage |
| 7 | **OSM / HOT exposure** — buildings, roads, bridges, helipads, populated places, health, education, hydropower | HDX + HOT Raw Data API, **ODbL** | Everything counted; routing network |
| 8 | **IMERG or CHIRPS** | NASA GES DISC / UCSB CHC | The rule-out evidence |

### 6.5 High value (9)

**ICIMOD glacial lake + PDGL inventory** (47 PDGLs; DOI 10.26066/RDS.1971946 / 1971950) — **Scout's population** · **HMAGLOFDB** (697 GLOFs 1833–2022, `github.com/fidelsteiner/HMAGLOFDB`, Zenodo 10.5281/zenodo.7271187) · **Copernicus EMS EMSR927** — validation; Syapru Besi AOI >240 destroyed, 32 damaged, WorldView-3 27/08 05:05 UTC · **UNOSAT** mudflow extent, 26–27 Aug 2026 · **Microsoft AI for Good** building damage via HDX, `independence_group: cv_damage_vhr` · **WorldPop 100 m**, CC BY 4.0 · **Vantor Open Data** WorldView pre/post (`10300100C86CED00`, `10500100364E8400`, `B030001100CF1610`), `s3://vantor-opendata/events/Nepal-Flooding-Aug-2026/` no-sign-request, **CC BY-NC 4.0** · **Planet Crisis Response**, `s3://us-west-2.opendata.source.coop/planet/disasterdata/nepal-flash-flood-2026-08-26/`, CC BY-NC 4.0 · **OCHA COD-AB** Nepal ADM2 v02, CC BY-IGO.

### 6.6 Depth (11)

Copernicus DEM GLO-30 (Scout's national screening) · OPERA RTC-S1 · USGS ANSS · ERA5-Land · IHME gridded population · GHSL / Meta HRSL · Landsat 5/7/8/9 · BIPAD (no public API — hand-curated CSV) · DHM river watch (web pages, not an API) · OpenAerialMap · Google Flood Forecasting API (free, CC BY 4.0, **waitlisted**).

### 6.7 Replay store

`data/replay/bhotekoshi_2026_08/` — the **real** OPERA and Sentinel-1 granules covering 27–28 August 2026, with a manifest and checksums verifying against source.

### 6.8 Excluded

Any paid API · Google Earth Engine as a runtime dependency (auth flow is a demo-day liability) · Google Photorealistic 3D Tiles (poor coverage in high Rasuwa) · any real personal data.

### 6.9 Synthetic — declared

Institutional contact lists matching the real distribution — DDMC duty officer, DHM divisional hydrologist, local administration, hydropower operator, police post, health post, school, community focal point — with non-routable numbers.

### 6.10 Licence stack

Most restrictive term wins per derived layer. Outputs mix ODbL (share-alike), CC BY, CC BY-NC and CC BY-IGO. NC-derived products live in a separate directory so the clean layers stay reusable. Ship a per-layer licence table, following the structure used by `hotosm/venezuela_eq_2026`.

---

## 7. RAG

ChromaDB, persistent, **two collections**.

| Collection | Contents | Job |
|---|---|---|
| `science` | HMAGLOFDB, ICIMOD PDGL report, ICIMOD Thame assessment, NHESS 2026 Thame paper, Taylor 2023, Shrestha 2023, Rounce 2016, Veh 2019, Mergili r.avaflow | Ground every method claim in a citation |
| `events` | Kathmandu Post, Al Jazeera, Reuters, ICIMOD releases, DHM bulletins, USGS ANSS, EMSR927, OSM activation wiki, BIPAD extracts, geopera docs **including the retracted version** | Precedent, under a hard date filter |

Metadata: `source_org`, `url`, `published_at`, **`published_ts` (int epoch)**, `claim_type` ∈ `{reported, official, analysis, retracted}`, `independence_group`, `geo`, `lang`.

Chunking: `RecursiveCharacterTextSplitter(800, overlap=120)` for news; papers split on section headings first, then recurse. Every retrieved chunk passes an injection filter before entering a prompt; drops are logged.

---

## 8. Channels

### 8.1 The board

Next.js 15, TypeScript strict, maplibre-gl, deck.gl, recharts, zustand, tailwindcss, **GeoLibre embedded**.

Routes: `/` board · `/preparedness` standing profiles · `/gate` approver · `/trace` rendered trace · `/build` progress.

**GeoLibre:** fork the public `giswqs/nepal-flash-floods` project (Vantor pre/post COGs, OPERA disturbance overlay, 3D terrain over satellite basemap, working swipe). **Credit Qiusheng Wu.** Generate `dist/sanket.geolibre.json` from Python via `load_project` → `add_cog`/`add_geojson` → `save_project`. **Our addition: the modelled inundation polygon over the observed extent** — a live validation figure, not a claim. Three fixed camera bookmarks: source zone ~5,600 m, Rasuwa Gadhi / Miteri Bridge, Syapru Besi. Vertical exaggeration **1.6**, value displayed.

**Terrain option B:** terrarium tiles from our own HMA 8 m DEM (`rio rgbify --format terrarium`), offered as a toggle labelled "open terrain, 8 m, NASA HMA".

**Four charts:** lake area 2016→now with cloud gaps shaded and change points marked · rainfall percentile vs 20-year climatology with both event dates marked · lead-time distribution with a line at 30 minutes · agent run history.

**Performance:** COGs via TiTiler, never full GeoTIFFs in the browser · vectors as PMTiles · every scenario frame precomputed · test on the demo laptop, on battery.

**2G fallback:** 4 KB text page, same content, Nepali available.

### 8.2 WhatsApp

**Twilio Sandbox.** Sending `join <code>` opens a **24-hour customer service window during which free-form text and media can be sent without a template.** That is the opt-in and the mechanism.

Practical: free trial accounts include 100 WhatsApp messages · sandbox sessions expire three days after joining · the sandbox number can be country-restricted, so **test delivery to a Nepali number on day one** · production path is Meta Cloud API with approved utility templates.

**Three tiers, slot-filled from Explainer output, never free composition:**

| Tier | Recipient | Content |
|---|---|---|
| 1 | Resident subscriber | Nepali, settlement, arrival time, one action, **plus the inundation map image** |
| 2 | Institutional | Arrival times per settlement, basis, confidence, evidence age, "this is a scenario", link to full evidence, **and what the system refused to conclude** |
| 3 | **Approver** | The gate request: attribution, counterfactual, flip point, before/after image, `Reply APPROVE <run_id>` |

**The gate over WhatsApp** is the design decision worth defending: a duty officer at 03:00 has a phone, not a laptop. Twilio inbound webhook → Flask route → match `run_id` and sender against `gates` → record approver identity, timestamp, decision → release the Actor's queued sends. Unmatched or unauthorised replies are logged and ignored.

`STOP` unsubscribes and is honoured before any send. Cooldown applies to WhatsApp as to every channel.

### 8.3 Voice and SMS

`gpt-audio` / Azure TTS generating real Nepali audio, ~22 seconds, arrival time interpolated into a **template with slots**. Dialler simulated and declared; audio real. SMS at 140 characters, Nepali, simulated gateway, declared.

---

## 9. Replay mode

A corridor flag that swaps the trigger source from live CMR polling to a local store of **real granules from the actual August 2026 event**, released on an accelerated clock with `as_of` advancing.

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

**Replay the barrier lake, not the 26 August collapse.** The collapse was unpredictable and the system would not have caught it; replaying it would be dishonest theatre. The barrier lake formed on the 27th and began overflowing on the 28th — **over a day of genuine lead time on an impoundment visible from orbit**, which is exactly the window the system exists for.

**Only the clock is simulated.** Granules, DEM, exposure layers and solver outputs are real, and **the agents run unmodified** — Watcher classifies for real, the Investigator picks its own tool path for real, the Verifier vetoes because the contradiction is genuinely in the evidence.

**Honesty rules, disqualification-adjacent:** persistent replay banner on the board, visually distinct · `REPLAY` marker on every trace line · `[REPLAY — TEST]` prefix on every outbound message · say it out loud before starting · the Solution Sheet's real-vs-mocked list records: data real, clock simulated, dialler simulated, WhatsApp real, contacts synthetic.

---

## 10. Full stack

**Agents & models** — `litellm` (Router; the only place a provider is named) · `smolagents` (sandbox only) · Ollama (offline lane) · `chromadb` · `sentence-transformers`

**Autonomy** — `APScheduler` · SQLite (queue + state) · `earthaccess` (CMR) · `structlog`

**Geospatial** — `rasterio` · `rioxarray` · `xarray` · `geopandas` · `shapely` · `pyproj` · `pysheds` · `whitebox` · `pystac-client` · `odc-stac` · `torch` · `rio-cogeo` · `rio-rgbify` · `titiler` · `omnicloudmask` · `omniwatermask` · vendored `route1d.py` and `swe2d_torch.py`

**Data** — `duckdb` (spatial, httpfs) · GeoParquet · COG · PMTiles

**API & channels** — `Flask 3` · `gunicorn` (gevent) · `pydantic 2` · SSE · `twilio`

**Board** — `Next.js 15` · TypeScript strict · `maplibre-gl` · `deck.gl` · `recharts` · `zustand` · `tailwindcss` · **GeoLibre embedded**

**Published** — `sanket-mcp` (twelve tool schemas over MCP) · HuggingFace dataset (corridor lakehouse + provenance registry, per-layer licence table)

**Quality** — `ruff` · `black` · `mypy --strict` · `pytest` · `import-linter` · pre-commit · CI

**On agent frameworks:** hand-rolled loop by default. A two-hundred-line loop you fully understand is worth more under questioning than a framework you cannot explain. LangGraph acceptable if preferred; be able to say why. **CrewAI is out** — role-play framing is a narrative device with real token cost.

---

## 11. Engineering standards

**No comments. None.** No inline, no block, no `# TODO`, no commented-out code, no section banners. If code needs explanation, the names are wrong or the function is too big.

Type hints on every Python signature; `mypy --strict` on `core/` and `analysis/`. TypeScript strict, no `any`. Functions under 40 lines, files under 400. Pure functions where possible, I/O at the edges. One responsibility per module. Pydantic at every boundary. Typed exceptions from `core/errors.py`, never bare `except`. `structlog`, never `print`. Config in `config.py` and `.env`. README per package — **that is where explanation lives.**

---

## 12. Limitations

**Cannot predict a GLOF or an ice-rock avalanche.** Triggers are stochastic and sub-satellite-scale.

**Cannot attribute any individual event to climate change.** May report a variable exceeded its baseline; the sentence ends there.

**Cannot claim GLOF frequency is increasing.** Veh et al. 2019 found unchanged moraine-dammed GLOF frequency in the Himalaya; HMAGLOFDB describes the evidence as ambiguous. What is supported: lakes are growing, downstream population has grown, therefore **exposure** has increased.

**Cloud and revisit.** Sentinel-1 at 6–12 days means a lake can form and drain between passes — apparently what happened at Purepu in July 2023. In steep terrain, SAR layover and shadow can obliterate the valley floor.

**Resolution.** 10 m cannot reliably detect lakes below ~0.003 km². The Thame lake was ~0.05 km².

**DEM vintage.** Even 8 m HMA predates the event. Post-event routing is wrong in ways we cannot correct.

**Volume estimation.** Large error bars on a small impoundment; external estimates unverified by us. Hence a scenario range, not a number.

**Simplified hydraulics.** A shallow-water solver is not a two-phase debris flow. The Thame flood carried debris more than 80 km.

**Exposure vintage.** WorldPop and OSM lag badly in remote mountain districts. Population is modelled usual residence and cannot show post-26-August displacement.

**Transboundary blindness.** No ground data, no gauges, no guaranteed imagery sharing. A diplomatic problem, not a technical one.

**Validation set of four events.** Any accuracy figure would imply more rigour than exists.
