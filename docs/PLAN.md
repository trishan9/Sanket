# SANKET — Build Plan

Prepared 3 September 2026 · Response to `05-MASTER-BUILD-PROMPT.md` FIRST ACTION
Status: **awaiting approval before Phase 0**

---

## 1. Interpretation

SANKET is a standing autonomous watch, not an application. The defining property is that
no human input path exists to start a run: a daemon ticks on a per-basin cadence, reacts
to OPERA granules published to NASA CMR, and sweeps 47 potentially dangerous glacial lakes
weekly. Everything else — the agents, the board, the gate — hangs off that.

The engineering centre of gravity is not the LLM work. It is the deterministic layer
underneath it: a terrain-conditioned DEM, a stage–volume curve, a breach hydrograph, a
routed flood, and an exposure count per settlement. The LLM chooses which of those
functions to call and in what order, and never computes a number itself. That division is
what makes the trace defensible under questioning, and it is what I will protect when
phases run long.

The cost design is the second load-bearing idea. Tier 0 and Tier 1 make zero model calls,
so 99% of the system's activity is free. One small classification call stands between
cheap watching and expensive investigating, and it exists because radar layover, wet-snow
backscatter and orbit geometry all look like change and are not.

The third is refusal. The Verifier runs on a different model family from the planner,
cannot author a claim that is not already in the ledger, and is expected to emit
`insufficient — no claim issued` on the contested cause of the 26 August event. The
Explainer then makes the decision interrogable — attribution decomposed from the actual
decision function, counterfactuals looked up from a precomputed grid, and a flip point.
Neither is narrated by a model; both are computed in Python and rendered.

Above WATCH the system stops. A named district officer approves over WhatsApp, or nothing
goes out. I will build the gate early enough that it is demonstrably load-bearing rather
than decorative, and I will keep every mocked component on an explicit list.

---

## 2. Verification performed before writing this plan

| Claim in the brief | Status | Evidence |
|---|---|---|
| `geo-pera/bhotekoshi-2026-reconstruction`, MIT | **Confirmed** | GitHub API: `spdx_id: MIT`. Tree contains `sim/scripts/route1d.py`, `swe2d_torch.py`, `xsections.py`, plus `s2_masks.py`, `superelevation.py`, `run_metrics.py`, `stereo_dh.py` |
| `giswqs/nepal-flash-floods` | **Exists — not on GitHub** | Hosted on GeoLibre's sharing service: `https://share.geolibre.app/giswqs/nepal-flash-floods.geolibre.json`, plain GET, 38.9 KB. My GitHub search 404'd because the page renders client-side. Fetched **once as a read-only styling reference**; not committed, not a runtime dependency |
| GeoLibre ships a built frontend | **Confirmed** | The `geolibre==2.9.0` wheel bundles `geolibre/static/app/` — 206 MB, `index.html` plus Vite assets. **Self-hosting needs no clone and no `npm run build`** |
| Vantor scenes exist at the spec's catalog IDs | **Confirmed by bucket listing** | 55 objects under `events/Nepal-Flooding-Aug-2026/`. All three IDs present, plus 13 further scenes and two ~20 GB stereo pairs |
| GeoLibre Python API | **Confirmed against the shipped 2.9.0 wheel**, not repo HEAD | `class Map`, `load_project`, `save_project`, `to_project`, `add_cog`, `add_geojson`, `add_pmtiles`, `add_geoparquet`, `add_raster`, `add_basemap`, `fly_to`, `fit_project_bounds`, **`split_map`**. Signatures recorded in `PROGRESS.md` |
| `fidelsteiner/HMAGLOFDB` + Zenodo 7271187 | **Confirmed** | Both HTTP 200 |
| NASA CMR `OPERA_L3_DSWX-S1_V1` collection | **Confirmed** | CMR collections endpoint returns the collection |
| Planetary Computer `sentinel-2-l2a`, anonymous | **Confirmed** | STAC collection endpoint 200 |
| HDX `hot_flood_npl` | **Confirmed** | CKAN `package_show` 200 |
| Vantor open data S3, no-sign-request | **Confirmed** | Anonymous `list-type=2` on `vantor-opendata` 200 |
| Full Python dependency set resolves | **Confirmed** | `uv pip compile` resolves 301 pkgs on 3.11, 316 on 3.12, no conflicts |

**Not yet verifiable — needs credentials:** the hackathon Azure endpoint and its model list
(`gpt-5.5`, `grok-4.6`, `gpt-audio`, `DeepSeek-V4-Flash`, `DeepSeek-V4-Pro`), Groq model
availability (`groq/compound`, `openai/gpt-oss-20b`, `openai/gpt-oss-120b`,
`qwen/qwen3-32b`), Twilio sandbox, NASA Earthdata. Phase 0 exit criteria include a live
`curl` against both providers and recording the **actual** model lists in `PROGRESS.md` —
every model name above is treated as unverified until that passes.

---

## 3. Environment as found

| | |
|---|---|
| Platform | Arch Linux, kernel 7.1.9 |
| System Python | **3.14.7** — too new for the geospatial stack |
| Node / npm | v26.8.1 / 11.19.0 |
| uv | 0.12.7 |
| GPU | NVIDIA GTX 1650, **4 GB VRAM** |
| RAM | **7 GB total, ~2 GB free** |
| Disk | 74 GB free on `/home` |
| Ollama | **not installed** |
| Git | **not a repository** |
| Credentials | **none present** — no env vars, no `.netrc`, no `.env` |

Three of these change the build and are carried into Assumptions and Open Questions:
RAM rules out the specified local model, VRAM constrains the 2D solver grid, and the
system Python must not be used.

---

## 4. Pinned dependencies

Python **3.12** via `uv` (see Assumption 1). Resolved and conflict-free as of 3 Sep 2026.

**Agents and models**
```
litellm==1.99.0
smolagents==1.26.0
chromadb==1.5.9
sentence-transformers==6.0.1
```

**Autonomy and service**
```
apscheduler==3.11.3      structlog==26.1.0     pydantic==2.13.5
flask==3.1.3             gunicorn==26.2.0      gevent==26.8.0
twilio==9.11.0           mcp==2.1.1            pyyaml / httpx / tenacity
```

**Geospatial**
```
rasterio==1.5.1          rioxarray==0.23.0     xarray==2026.7.0
geopandas==1.1.4         shapely==2.1.2        pyproj==3.7.2
pysheds==0.5             whitebox==2.3.6
pystac-client==0.9.0     odc-stac==0.5.3       earthaccess==0.18.0
rio-cogeo==7.0.2         rio-rgbify==0.4.0     titiler-core==2.2.1
omnicloudmask==1.7.1     omniwatermask==0.6.2
duckdb==1.5.5            geolibre==2.9.0
numpy==2.5.2             scipy==1.18.1
torch==2.14.0            (CPU wheel default; CUDA cu124 optional, see Assumption 6)
```

**Quality**
```
ruff · black · mypy · pytest · pytest-asyncio · import-linter · pre-commit
```

**Board** — Next.js 15 App Router, TypeScript strict, `maplibre-gl`, `deck.gl`, `recharts`,
`zustand`, `tailwindcss`, GeoLibre embedded.

Under Python 3.11 the same set resolves with `rasterio==1.4.4` and `earthaccess==0.17.0`;
both are acceptable if 3.11 is mandated.

---

## 5. The fifteen phases

Effort is agent-working-hours, assuming credentials are present when the phase starts.
Phases 1 and 12 dominate; this matches the brief's own warning about Phase 1.

### Phase 0 — Scaffold, both providers, router, logger, walking skeleton · **6 h**

**Files** `pyproject.toml` · `.pre-commit-config.yaml` · `.github/workflows/ci.yml` ·
`.importlinter` · `core/config.py` `errors.py` `provenance.py` ·
`agent/router.py` `budget.py` `cache.py` `trace.py` · `watch/daemon.py` (minimal) ·
`api/app.py` · `board/` shell + `/build` · `tests/test_no_comments.py`
`tests/test_provider_isolation.py` · README per package

**Tools** uv, ruff, black, mypy, pytest, import-linter, curl

**Deliverables** LiteLLM Router with all six lanes (`sanket-plan-local` dropped, see Phase 13), cross-provider fallbacks, tpm/rpm,
`simple-shuffle`, cooldown 60 s, `num_retries=3`, `allowed_fails=2`, timeout 45 ·
budget tracker splitting tokens and NPR by provider · append-only trace logger written
**before** the loop · walking skeleton: scheduled tick → real `stage_volume` on the real
DEM → `write_status` → board changes.

**Exit** `pytest`, `mypy --strict`, `ruff` clean · zero comments in any source file,
asserted by test · both providers reachable and both **actual** model lists recorded in
`PROGRESS.md` · a lint rule fails the build if any file but `router.py` imports a provider
SDK · the skeleton runs on a timer with nobody pressing anything and the board visibly
changes · trace shows a real run with provider and cost attribution.

**Risk** Provider model names unverified. If `gpt-5.5`/`grok-4.6` are absent from the
endpoint, lane assignments change here, not later.

---

### Phase 1 — Data acquisition and EDA · **14 h · the longest phase**

AOI `[85.10, 27.80, 85.45, 28.55]`; final bbox recorded in the corridor YAML.

**Files** `core/connectors/{cmr,opera,stac,hdx,icimod,hmaglofdb,dhm,worldpop,usgs}.py` ·
`data/bronze/` `data/silver/` `data/manifests/` · `notebooks/00_env` `01_inventory`
`02_dem` `03_eo` `04_precip` `05_exposure`

**Deliverables** Connectors returning provenance-stamped bronze artifacts with fetch
manifests and sha256 checksum-skip · bronze→silver reprojection to **EPSG:32645** as
GeoParquet/COG · the eight must-have datasets plus the high-value set.

**Exit** every Tier-1 dataset in `bronze/` with a manifest, or listed pending with a
working link · all promoted to `silver/` · notebooks 01–05 execute top to bottom with
outputs committed · **cloud-fraction distribution documented** — this decides how much
optical is usable at all · data-quality summary in `PROGRESS.md`.

**Risk** Highest in the build. Earthdata registration gates the HMA DEM, all OPERA and
IMERG, and **has no fallback**. Memory-constrained: all raster reads windowed/chunked.

---

### Phase 2 — Lakehouse, provenance, corridor registry · **6 h**

**Files** `core/registry/*.yml` · `core/watch/{bhotekoshi,thame,tilgau}.yml` ·
`core/lakehouse.py` · `core/publish.py` · gold builders ·
`tests/test_as_of_firewall.py` `tests/test_no_admin_geometry_in_scoring.py`
`tests/test_second_corridor_loads.py`

**Deliverables** Full provenance contract schema including `cannot_tell_you` and
`independence_group`, Pydantic-validated at import · `query(sql, *, as_of)` filtering
**and counting** post-cutoff rows into a rejection log.

**Exit** every silver layer has a validated contract · `as_of` filtering excludes
post-cutoff rows with a non-zero rejection count · **a second corridor YAML loads with no
code change** · publish produces a valid dataset directory · admin boundaries proven
display-and-filter-only by test.

---

### Phase 3 — Terrain and hydraulics · **12 h**

**Files** `analysis/hydro/{dem,xsections,stage_volume,breach,route1d,swe2d_torch,scenarios}.py` ·
`forked/geopera/` vendored · `notebooks/06_calibration`

**Deliverables** DEM conditioning (fill → flow dir → flow accum → channel → HAND) ·
`route1d.py` and `swe2d_torch.py` **vendored from `geo-pera/bhotekoshi-2026-reconstruction`
(MIT, confirmed)** with licence headers retained · scenario grid precomputed across
volume 0.5–5.0 Mm³ × breach 5 min–6 h as COGs · calibration against observed flow heights
(geo-pera reports median ~70 m through the confined gorges; bank measurements 40–134 m at
Rasuwagadhi) with **residuals plotted**.

**Exit** channel network matches the real river · stage–volume curve at the barrier lake
location · scenario grid COGs load under 200 ms · calibration residuals with a stated
error range · `route1d` under 10 s on CPU · every output `claim_type: scenario` · DEM
vintage recorded on every routing output.

**Risk** 4 GB VRAM caps the `swe2d_torch` domain. Mitigation: tile the domain, or run the
grid precompute on CPU overnight — it is a one-off, and `route1d` is the always-works path.

---

### Phase 4 — EO detection and baselines · **10 h**

**Files** `analysis/eo/{masks,dswx,dist,mndwi,baselines,changedetect,lake_series,agreement}.py`

**Deliverables** OmniCloudMask/OmniWaterMask wrappers · our own MNDWI+Otsu detector tagged
`independence_group: sanket_optical` · **rolling 14-observation baselines per product per
tile with variance** · z-score change detection · lake area series with cloud-gap logging ·
per-pixel n-of-3 agreement raster.

**Exit** lake area series 2016→now · Purepu detected in the July 2023 / December 2024 /
June 2025 windows **or a documented explanation of why not** · baselines stored with
variance · cloud-gap log. No custom training, no YOLO.

---

### Phase 5 — Exposure, lead times, preparedness · **8 h**

**Files** `analysis/exposure/{cells,leadtime,isolation,preparedness,assembly}.py` ·
`notebooks/07_validation`

**Deliverables** Lead-time histogram and ECDF · road-egress isolation · **standing
preparedness profile per settlement across the full scenario range, available with no
event and no alert** · assembly-point candidates and routes · validation against
Copernicus EMS EMSR927 and UNOSAT with confusion matrix, IoU, precision, recall.

**Exit** lead times per settlement per scenario · histogram shows non-trivial population
under 30 minutes · a standing profile exists for every settlement at NORMAL · validation
notebook produces real metrics with stated caveats, **reported whatever the numbers are** ·
every count reports its dataset vintage and states that population is modelled usual
residence and cannot show post-26-August displacement.

---

### Phase 6 — The daemon · **8 h**

**Files** `watch/{daemon,scheduler,triggers,tiers,queue,state}.py` ·
`tests/test_tier01_zero_llm.py` `tests/test_crash_recovery.py` `tests/test_second_run.py`

**Deliverables** Full state schema (`basin_tiers`, `baselines`, `anomalies`, `runs`,
`notifications`, `gates`, `subscribers`) · CMR `updated_since` polling from
`last_granule_check` · hysteresis, cooldown-before-gate, fingerprinting
`hash(location_cell, feature_id, change_signature)` · cold start with `warming_up` ·
crash recovery re-queueing from the last completed tool call.

**Exit** `sanket watch start` runs unattended with **no human input path** · a new granule
triggers Tier 1 with nobody pressing anything · **Tiers 0 and 1 make zero LLM calls,
asserted in a test** · killing and restarting recovers the queue · **the second run on the
same anomaly behaves differently from the first**.

---

### Phase 7 — Scout · **5 h**

**Files** `agent/scout.py` · `analysis/eo/national_sweep.py`

**Exit** all 47 PDGLs swept in a single run, on Groq, with cost recorded · basin tiers
written with drivers explaining each assignment · **promoting a corridor demonstrably
changes its tick cadence** · the board's national panel shows sweep date and tier counts ·
standing exposure ranking across all 47.

---

### Phase 8 — Investigator and Verifier · **14 h**

**Files** `agent/loop.py` `verifier.py` `ledger.py` · `agent/tools/*` `schemas.py` ·
`agent/rag/{store,ingest,retrieve,guard}.py` · `api/sse.py`

**Deliverables** `MAX_STEPS = 10` hand-rolled loop · twelve tools with Pydantic
`args_schema` and signed provenance envelopes · Verifier's four checks and veto, **rejecting
in code any claim whose statement is not already in the ledger** · ChromaDB with two
collections, `BAAI/bge-m3`, **`published_ts` as integer epoch**, injection filtering with
logged drops, the geopera retraction indexed as `claim_type: retracted` · Flask SSE with
`X-Accel-Buffering: no` on gevent workers.

**Exit** full investigation end to end from a real trigger · **two traces showing genuinely
different tool sequences for different anomaly types** · Verifier produces
`insufficient — no claim issued` on the contested 26 August attribution · a test proves the
Verifier cannot introduce a claim absent from the ledger · SSE streams incrementally ·
one investigation under 60 s warm.

**Risk** `bge-m3` is ~2.2 GB — heavy for 7 GB RAM. See Open Question 3.

---

### Phase 9 — Explainer and the sandbox · **8 h**

**Files** `agent/explainer.py` `sandbox.py` · `tests/test_attribution_matches_function.py`
`tests/test_register_consistency.py` `tests/test_sandbox_cannot_act.py`

**Deliverables** Attribution decomposing the **actual** decision function into per-term
contributions in Python · counterfactuals from the precomputed grid · flip points ·
what-would-change-my-mind including which questions are irrelevant · three registers
(`PublicNote`, `EvidencePack`, `Scripts` — template-with-slots) · smolagents `CodeAgent`
sandbox, read-only DuckDB, no network, no writes, 10 s timeout.

**Exit** attribution numbers match a direct computation of the decision function, by test ·
counterfactuals match a direct grid lookup · **a test compares numeric claims across all
three registers and fails on divergence** · no fact in any rendering that is not in the
ledger · a veto appears in all three registers · a follow-up question with no tool returns
a correct answer with the Python shown · **a test proves the sandbox cannot write status,
trigger a notification or alter a gate decision** · deleting `sandbox.py` leaves every
other test green.

---

### Phase 10 — Actions, the gate, and WhatsApp · **10 h**

**Files** `actions/{board,gate,voice,sms,whatsapp,inbound,scripts_ne,templates_wa}.py`

**Exit** WATCH writes autonomously and the board changes · ALERT stops at the gate with no
outbound action · **a real WhatsApp message with an attached map image arrives on a real
phone** · **replying `APPROVE <run_id>` from the registered approver's number releases the
sends; replying from any other number does not** · `STOP` unsubscribes and is honoured
before the next send · cooldown blocks a second message inside the window · delivery status
written back to `notifications` · real Nepali audio plays.

**Risk** Twilio sandbox country restrictions. Brief says test delivery to a Nepali number
on day one — I will fold this into Phase 0 rather than waiting for Phase 10.

---

### Phase 11 — Replay mode · **5 h**

**Files** `watch/replay.py` · `core/watch/bhotekoshi.replay.yml` ·
`data/replay/bhotekoshi_2026_08/` with manifest and checksums

**Exit** the full chain runs end to end from replay with **no human input beyond starting
it** · **running it three times produces at least two different tool sequences** — if
identical every time the Investigator is over-constrained and the prompt gets loosened ·
board unambiguously marked as replay · every outbound message prefixed `[REPLAY — TEST]` ·
`REPLAY` marker on every trace line · manifest checksums verify against the real granules.

Replays the **barrier lake of 27–28 August, not the 26 August collapse** — the collapse was
unpredictable and replaying it would be dishonest theatre.

---

### Phase 12 — The board · **14 h**

**Files** `board/app/{page,preparedness,gate,trace,build}` · `board/components/*` ·
`api/routes/*` · `board/geolibre/build_project.py` → `dist/sanket.geolibre.json`

**Deliverables** Status header with last-checked and evidence-age always visible ·
settlement tiles · "what the agent found" · **the WHY panel** · four charts (lake area with
cloud gaps shaded, rainfall percentile vs 20-year climatology, lead-time distribution with
a line at 30 minutes, run history) · national panel · cost per run split by provider with
the all-`gpt-5.5` counterfactual · `/preparedness` at NORMAL · `/gate` with the Ask panel ·
`/trace` colour-coded by agent, failures in red, retries indented · Nepali toggle ·
**4 KB text fallback**.

**GeoLibre — decided.** `dist/sanket.geolibre.json` is a **build artifact**, regenerated by
`build_project.py` whenever the scenario grid or the lake polygons change. It is never
fetched from a third party at runtime — a hosted project would be a demo-day liability.
Phase 1 already pulls every layer it needs, so this script only arranges assets we hold:
**budget 30–60 minutes.** If it runs longer, something upstream is missing and that is the
real problem to fix.

**Self-hosted, not iframed.** The Bad Day requires the board to work with the network
unplugged, so `web.geolibre.app` is never embedded. The `geolibre==2.9.0` wheel already
bundles the built frontend at `geolibre/static/app/` (206 MB, `index.html` plus Vite
assets), so **no clone and no `npm run build` are required** — Flask serves that directory
and points it at a locally served project file. The hosted embed stays a fallback only.

**Scene selection — decided by listing the bucket, not by guessing.** All three catalog IDs
in the brief are present, but their dates matter:

| Scene | Acquired | Cloud | Note |
|---|---|---|---|
| `10300100C86CED00` | 2021-10-16 | 22% | pre-event, five years stale |
| `10500100364E8400` | 2023-09-17 | 46% | pre-event |
| **`10300100FCB83600`** | **2024-05-29** | **15%** | **best pre-event scene in the bucket** |
| `B040001100882F10` | 2026-08-27 05:05 | 79% | post-event; **the acquisition CEMS EMSR927 used** |
| `B030001100CF1610` | 2026-08-28 | 79% | post-event |

The reference project pairs 2021 and 2023 against 2026-08-28. I will choose the pair by
inspecting actual footprints over Rasuwa Gadhi in Phase 12 and **record which scenes were
used and why** on the board. The 79% cloud on both post-event scenes is not a defect to
hide — it is the monsoon-blindness argument the whole system rests on, and it belongs on
screen next to the swipe.

**Attribution.** README and attribution page credit **GeoLibre — Qiusheng Wu,
`opengeos/GeoLibre`, MIT**, because we use his software. His Nepal project is **not**
credited unless we actually adopt its layer arrangement, and if we do, the credit says
specifically that is what was taken.

**Exit** board updates within seconds of a status write with no human action · self-hosted
GeoLibre loads with working `split_map` swipe and our modelled inundation overlay, **with
the network disconnected** · three camera bookmarks · vertical exaggeration 1.6, value
displayed · Nepali toggle works across charts, tiles and the WHY panel · **the 4 KB
fallback renders under a throttled connection, demoed live** · `/trace` renders a complete
run legibly with the failure and recovery visible · every displayed number carries its
source and vintage · a `scenario` never renders in the same visual style as an
`observation`, enforced in the renderer.

---

### Phase 13 — Resilience and provider failover · **5 h**

**Ladder — decided, local rung dropped:** Azure → Groq → **deterministic mode** → last
known good, **each step stamped in the trace**.

The brief's `sanket-plan-local` Ollama lane is removed rather than shipped as dead config.
`gpt-oss-20b` needs 13–16 GB; this machine has 7 GB RAM and 4 GB VRAM. Wiring a lane that
has never executed and cannot execute here would be config theatre, and claiming an offline
model path on stage that was never run is exactly the kind of thing the honesty rules
exist to prevent.

**What replaces it.** Deterministic mode is a real rung, not a placeholder: with no provider
reachable, the daemon keeps running, Tier 0 and Tier 1 need no model at all, change
detection still produces a z-score, the precomputed scenario grid still yields arrival
times, and the board still updates from the last verified status with its age in hours.
**The offline story stays true — it just no longer involves a model.** The Solution Sheet
records the substitution.

**Exit** revoking the Azure key mid-run: the investigation completes on Groq and the trace
records the switch · both providers unreachable: deterministic mode still updates the
board and the trace records `degraded: deterministic` · network physically disconnected:
last known good served with age in hours, and the self-hosted board still renders.

**Declared:** the shared Azure key cannot be genuinely revoked — fifteen teams use it — so
that failover is demonstrated by injecting an invalid key into the router deployment at
runtime, which exercises the identical code path. The Groq key is ours and is revoked for
real.

---

### Phase 14 — Validation and deliverables · **10 h**

Complete notebooks 06 and 07 · publish confusion matrix, IoU, precision, recall against
EMSR927 · calibration residuals plotted · an honest reading of where and why the model
fails · `mcp/server.py` exposing the twelve tool schemas, published as `sanket-mcp` ·
`core/publish.py` executed to a HuggingFace dataset with a per-layer licence table ·
clean trace capture with **failed steps retained** · one-page Solution Sheet including the
**blunt real-vs-mocked list** · README with a "Brought in" section crediting GeoLibre and
Qiusheng Wu / opengeos, the geo-pera solvers, HMAGLOFDB, LiteLLM, smolagents and every
library · 60-second video.

**Exit** real validation numbers published with caveats · an external MCP client can call
`stage_volume` and `exposure_at` against the published server and get correct results ·
full demo runs six times without failure · trace legible and unsanitised · Solution Sheet
complete · open contribution links live.

---

**Total ≈ 135 agent-hours.** Phases 1, 3, 8 and 12 are 40% of it. Phases 0, 2, 6, 7, 9, 11
and 13 are largely independent of external credentials once Phase 0 passes.

---

## 6. Assumptions

1. **Python 3.12, not 3.11.** System Python is 3.14.7, which the geospatial stack does not
   support. Current `rasterio==1.5.1` and `earthaccess==0.18.0` both require `>=3.12`.
   3.11 resolves too, with `rasterio==1.4.4` / `earthaccess==0.17.0`. I will use 3.12 via
   `uv` unless told otherwise. Low risk either way.
2. **The repo root is `/home/trishan/Work/TSN-Hackathon`**, treated as `sanket/`. The five
   spec documents stay where they are; I will not move them. `git init` on approval.
3. **Every provider model name in the brief is unverified** and treated as a hypothesis
   until the Phase 0 `curl` returns a real model list. Lane assignments adapt to what the
   endpoint actually serves.
4. **Casualty and volume figures are quoted with their date, always**, and never restated
   as current. The barrier lake volume is carried as a scenario range, never a number.
5. **The scenario grid is precomputed and declared as caching** on the board, the Solution
   Sheet and on stage.
6. **torch installs as the CPU wheel by default.** CUDA cu124 is an opt-in extra; the
   4 GB GTX 1650 is treated as a bonus, never a requirement. `route1d` on CPU is the
   always-works path and gates the exit criteria.
7. **All raster I/O is windowed or chunked.** With ~2 GB free RAM, no full-scene reads.
   This is a correctness constraint here, not an optimisation.
8. **Institutional contacts are synthetic with non-routable numbers**, matching the real
   distribution. Real numbers used only for the two live WhatsApp demo endpoints the user
   supplies and opts in.
9. **The AOI is `[85.10, 27.80, 85.45, 28.55]`** until Phase 1 EDA refines it; the final
   bbox lands in `core/watch/bhotekoshi.yml`.
10. **Nepali strings are template-with-slots throughout.** No free composition reaches
    voice or SMS, and I will need a Nepali speaker to review the templates before the demo.

---

## 7. Open questions — resolved 3 September

**1. GeoLibre — RESOLVED.** The project does exist, on GeoLibre's sharing service rather
than GitHub: `https://share.geolibre.app/giswqs/nepal-flash-floods.geolibre.json`. Fetched
once as a read-only styling reference; not committed, not a runtime dependency.
**Decision: generate our own `dist/sanket.geolibre.json` from `build_project.py`** as a
build artifact, self-host the GeoLibre frontend, never iframe the hosted app. Detail in
Phase 12. My "roughly a day" estimate was wrong — Phase 1 already fetches every layer the
project needs, so this is 30–60 minutes of arranging assets we hold.

**2. Local model lane — RESOLVED. Dropped.** Ladder is Azure → Groq → deterministic → last
known good. Rationale and what replaces it in Phase 13.

**3. `BAAI/bge-m3` is ~2.2 GB and will be tight alongside everything else.**
Not blocking — lazy load, small batches, embeddings cached to disk so it is resident only
during ingest. Proceeding as specified.

**4. WhatsApp demo endpoints — OPEN, needs you.** I need at least one phone number joined
to the Twilio sandbox to act as the registered DDMC approver, and ideally a second as a
resident subscriber. The sandbox can be country-restricted, so **a Nepali number should be
tested on day one** — this has moved into Phase 0.

**5. Vantor scene pairing — OPEN, I decide in Phase 12.** The two post-event scenes are
both 79% cloud and the best pre-event scene (2024-05-29, 15% cloud) is not one of the three
the brief names. I will choose by footprint over Rasuwa Gadhi and record what was used.

---

## Working cadence

Continuous, with **four checkpoints**: I stop after Phase 1 (data), Phase 8
(Investigator and Verifier), Phase 10 (the gate) and Phase 12 (the board) — the four places
where a wrong turn is expensive to unwind. `PROGRESS.md` and `progress.json` are updated at
every phase boundary regardless. I also stop early, at any point, for a missing credential
or a failed exit criterion.

---

## 8. Where I think the brief is wrong, or optimistic

Stated plainly, as instructed.

**I was wrong about the GeoLibre fork, and about what it would cost.** I reported the
project as non-existent on the basis of a GitHub search; it is hosted on GeoLibre's sharing
service, which renders client-side. And my "roughly a day" figure ignored that Phase 1
already downloads every layer involved. Both corrected above. The brief was accurate on
every point I checked.

**"No comments. None." conflicts with vendoring MIT code.** The brief also requires the
geo-pera licence headers be retained. Those headers are comments. My reading: the rule
governs code we author, and vendored files under `forked/` keep their headers untouched —
stripping them would be a licence violation. The no-comments test will exclude `forked/`.
Flagging it so the exemption is a decision, not a slip.

**Phase 13's "revoke a key at runtime" is not fully testable on a shared endpoint.** I
cannot revoke the hackathon key — fifteen teams share it. Failover is demonstrated by
injecting an invalid key into the router deployment at runtime, which exercises the same
code path (cooldown on auth failure → fallback lane) and is declared as a fault injection
rather than a real revocation. The Groq key is ours and is revoked for real.

**The brief's local Ollama lane assumes hardware this build does not have**, and is dropped
rather than shipped as untested config. See Phase 13.

**"One investigation under 60 seconds warm" is optimistic on this hardware** if any tool
touches a fresh raster. Mitigation is aggressive caching of tool results and the
precomputed grid, both already in the design. If it does not hold I will report the real
number rather than tune the demo around it.

**Phase 1 at 14 hours is the estimate I trust least.** Earthdata registration, HDX API
shape and the Vantor bucket layout are all discoverable only by doing. If it overruns, it
overruns — the brief is right that compressing it is the wrong trade.

**A validation set of four events cannot support an accuracy claim**, and the brief already
says so. I will publish the EMSR927 confusion matrix with that caveat attached to the
number itself, not in a footnote.

---

## 9. Immediate blockers

Nothing can start until these exist. Detail in `MANUAL_DOWNLOADS.md`.

| Blocker | Blocks | Fallback |
|---|---|---|
| NASA Earthdata login | HMA 8 m DEM, all OPERA, IMERG — Phases 1, 3, 4, 6 | **None. Register first.** |
| Hackathon Azure key + base URL | Investigator, Verifier, voice — Phases 0, 8, 9, 10 | Groq-only, degraded |
| Groq API key | Scout, Watcher T2, Explainer — Phases 0, 7, 9 | Azure-only, unfair use |
| Twilio SID + auth token + two joined sandbox numbers | The gate, WhatsApp — Phase 10 | Simulated, weakens Signal 06 |

Phase 0 can begin with Groq and Azure keys alone. Earthdata is needed by Phase 1.

---

## Risk engine — additive plan

Added after the main build, per `08-UPDATE-PROMPT-RISK-ENGINE.md`. **Additive only:** new
modules in new files, existing modules gain functions rather than losing them, and the
existing twelve tools keep their exact signatures.

**Regression baseline: 98 non-network tests passing** (115 collected, 17 network-deselected)
at the moment the risk engine work started. That number may only go up.

**Blocker declared:** `07-RISK-ENGINE-IMPLEMENTATION.md` does not exist in this repository.
The 08 prompt instructs reading it first and says its Part 1 governs every claim the rest
may make. Built from 08's own specification instead, which is detailed enough to implement
against, and flagged to the user rather than silently inventing what Part 1 might have said.

**Sub-phase A — risk engine core.** `analysis/risk/{schemas,base_rates,observability,`
`susceptibility,cascade_graph,cascade_sim}.py`. Base rates are a real join of HMAGLOFDB's 773
events against the ICIMOD 2015 inventory's 3,624 lakes, stratified by dam type. Poisson rather
than Wilson intervals, because ice-dammed lakes recur and the rate legitimately exceeds one
event per lake — a binomial proportion cannot express that. All 47 PDGLs scored and ranked.

**Sub-phase B — meteorology.** `analysis/met/{percentile,anomaly,ruleout}.py` over 21 years of
CHIRPS monthly and the real August 2026 daily series. Temperature, freezing level and snowmelt
are not held by this system and are reported as unobserved rather than normal.

**Sub-phase C — levels and damage.** `actions/levels.py` five-level ladder with the old four
names accepted as aliases; `analysis/economics/damage.py` emitting ranges only.

**Sub-phase D — flash path.** `watch/flash.py`, reduced step budget of 4, short gate deadline,
auto-escalation on deadline. `agent/loop.py::investigate()` gains optional `max_steps`,
`tool_names` and `system_prompt` parameters whose defaults reproduce the existing behaviour
exactly.

**Sub-phase E — dashboards.** `/gov` technical view plus public-board extensions, backed by
new read-only endpoints in `api/risk.py`.

**Touched existing files, and why it is safe:** `agent/tools/schemas.py` and
`agent/tools/catalog.py` gain four appended tools; `ToolContext` moves to
`agent/tools/context.py` and is re-exported from `catalog` so every existing import keeps
working; `agent/loop.py` gains defaulted parameters; `actions/whatsapp.py`, `actions/actor.py`
and `actions/pipeline.py` gain an optional `corridor` argument used to render the real alert
card; `core/config.py` gains `public_base_url`; `api/app.py` gains routes. No existing
behaviour changes when the new arguments are omitted.

**Alert card, replacing the placeholder.** The gate and resident messages previously carried a
raw landscape satellite JPEG with no status and no Nepali. `analysis/render/floodmap.py` plus
`actions/alertcard.py` now render a real portrait card per settlement: hillshade from the real
HMA 8 m DEM, the real 1D Saint-Venant peak-rise raster over it, the settlement highlighted and
framed, status in English and Nepali, action text in both languages, and a `SCENARIO` watermark
with the DEM vintage.
