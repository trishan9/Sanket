# 06 — Data and Agents, in Plain English

For explaining SANKET to anyone — technical or not — using exactly what has been built,
not what is planned. Every claim below points at a real file and line number you can open.

**Read this first, one paragraph:** Today the system downloads real satellite and
government data, cleans it into one consistent format, and runs real physics/math on it
(how much water a landslide dam holds). That part is finished and running. The "AI reads
the data and decides what to investigate" part — the six agents described later in this
document — is designed in detail but **not yet written as code**. This document is honest
about that line, and marks every section as either **BUILT** or **PLANNED**.

---

## Part A — Every dataset, its format, and why we use it

| # | Dataset | File format | Resolution | What it actually shows | Fetched by |
|---|---|---|---|---|---|
| 1 | NASA HMA 8m DEM | GeoTIFF (`.tif`), float32 | 8 m | Ground elevation — the terrain shape | `core/connectors/opera.py` |
| 2 | OPERA DSWx-S1 | GeoTIFF, 4 bands (water mask, background water, confidence, diagnostic) | 30 m | Where there is surface water, seen by radar | `core/connectors/opera.py` |
| 3 | OPERA DIST-ALERT-HLS v1 | GeoTIFF, 8 bands (disturbance status, anomaly, confidence, date, etc.) | 30 m | Where the land surface changed recently | `core/connectors/opera.py` |
| 4 | Sentinel-1 RTC (radar) | GeoTIFF, VV + VH bands | 10 m | Radar backscatter — sees through cloud | `core/connectors/stac.py` |
| 5 | Sentinel-2 L2A (optical) | GeoTIFF, bands B03/B08/B11 + cloud mask | 10–20 m | Ordinary satellite photo bands, used to measure lake area | `core/connectors/stac.py` |
| 6 | ICIMOD PDGL + glacial lake inventory | Shapefile (`.shp/.dbf/.shx/.prj`) | vector (points) | The official list of 47 dangerous lakes, plus 3,624 catalogued lakes | `core/connectors/icimod.py` |
| 7 | HMAGLOFDB | CSV | tabular | 773 historical glacial flood events with dates, deaths, mechanism | `core/connectors/hmaglofdb.py` |
| 8 | HDX `hot_flood_npl` | GeoJSON (some zipped) | vector (points/lines/polygons) | Buildings, roads, bridges, hospitals — what's on the ground | `core/connectors/hdx.py` |
| 9 | HDX building damage | GeoJSON | vector (polygons) | Which buildings AI flagged as damaged after the flood | `core/connectors/hdx.py` |
| 10 | WorldPop | GeoTIFF | 100 m | Estimated number of people per grid cell | `core/connectors/worldpop.py` |
| 11 | CHIRPS monthly rainfall | GeoTIFF (Cloud-Optimized) | ~5.5 km | Rainfall by month, 2006–2026, for climate comparison | `core/connectors/chirps.py` |
| 12 | CHIRPS daily rainfall (August 2026) | GeoTIFF, gzip-compressed | ~5.5 km | Day-by-day rainfall around the flood, to check "did it rain" | `core/connectors/chirps.py` |

**In one sentence per format type:**
- **GeoTIFF** = a map where every pixel is a number (elevation, water/no-water, rainfall amount). This is what almost everything above is.
- **Shapefile / GeoJSON** = dots, lines, or shapes on a map with labels attached (a lake, a bridge, a building), rather than a grid of numbers.
- **CSV** = a plain spreadsheet — rows and columns, no map at all, used only for the historical events list.

---

## Part B — Cleaning and filtering, in very simple words

Every dataset goes through the same three-step journey. Think of it like: **buy groceries → wash and cut them → cook with them.**

### Step 1 — Fetch ("buy the groceries")
We ask each data provider (NASA, ESA/Copernicus, ICIMOD, HDX, WorldPop, UCSB) for exactly
the area and dates we need, not the whole world. Two cleaning tricks happen right here:

- **We never download a whole satellite scene if we only need our small area.**
  `core/connectors/clip.py`, function `clip_remote()` (line 21) opens the file *remotely*
  over the internet and reads only the pixels inside our corridor's rectangle. A 1.6 GB
  satellite image becomes an ~18 MB file on our disk. This is the single biggest cleaning
  trick in the whole system — it's why 12 datasets fit in under 4 GB.
- **We only take the specific layers we need, not everything a satellite pass produces.**
  `core/connectors/opera.py`, function `select_links()` (line 74): one satellite pass can
  produce 4–8 different maps (water, confidence, cloud, disturbance date...). We pick out
  only the 2–3 we actually use.

Two datasets refused the "read remotely" trick and needed a different fix:
- **WorldPop's server won't let you ask for just part of a file.** `core/connectors/worldpop.py` line 19 downloads the whole national file to a temporary folder, cuts out our area, then deletes the big file. Net result on disk: 40 KB, not 400 MB.
- **CHIRPS daily rainfall files are zip-compressed**, so you can't peek inside them without downloading first. `core/connectors/chirps.py`, function `clip_gzipped()` (line 69) downloads, unzips, cuts out our area, deletes the temp file.

### Step 2 — Clean ("wash and cut")
`core/silver.py` is the one file that cleans everything, regardless of which dataset it
came from.

- **Put every map on the same grid.** Different satellites and agencies publish maps using
  different map projections (imagine one map measured in miles and another in kilometres,
  both claiming to show the same street). `reproject_raster()` (line 30) converts every
  single raster into one shared system, **UTM Zone 45N**, so that a distance measured on
  one map is directly comparable to a distance measured on another.
- **Mark missing data as missing, not as zero.** The DEM uses `-9999` to mean "no data
  here" (a hole in the terrain scan). `analysis/hydro/dem.py` line 66 rewrites every
  `-9999` as `NaN` ("not a number") so later maths doesn't accidentally treat a hole in the
  data as "sea level."
- **Unzip files that were secretly zip archives pretending to be GeoJSON.**
  `core/silver.py`, function `read_vector()` (line 73) — a real bug we hit: some
  HDX files ending in `.geojson` are actually zip archives. This checks and unzips
  automatically instead of crashing.
- **Only keep the clearest satellite photos.** Optical satellite images are mostly useless
  under cloud. Instead of downloading photos that are 90% cloud, we only fetch scenes
  where cloud cover is below a threshold (see Part D — cloud filtering).

### Step 3 — Use ("cook")
Only after both steps above does any number get used in a calculation. This is Part C.

---

## Part C — How data actually reaches "the agent" (the Evidence envelope) — BUILT

This is the mechanism, not a metaphor. Every piece of data that will ever be shown to an
AI model — or to a human on the board — gets wrapped in the same small structured package
before it goes anywhere. Defined in `core/provenance.py`.

```
{
  "value": { "max_volume_Mm3": 10.269, "base_elevation_m": 1745.4 },
  "provenance": {
    "source": "NASA HMA 8 m DEM (HMA_DEM8m_MOS)",
    "method": "barrier-constrained hypsometric fill...",
    "as_of_filter": "2026-09-02",
    "dataset_vintage": "2017-07-16",
    "independence_group": "hma_dem_terrain",
    "uncertainty": { "relative_error": 0.27 }
  },
  "claim_type": "model_output"
}
```

**In plain words: every number carries a passport.** It says where it came from, when it
was measured, how it was calculated, how confident to be, and — critically — a label
(`claim_type`) that says what *kind* of number it is. There are six kinds
(`core/provenance.py` line 12):

| `claim_type` | Plain meaning |
|---|---|
| `observation` | Something a satellite or sensor actually measured |
| `correlation` | Two measurements that move together (doesn't prove cause) |
| `model_output` | Something we calculated from measurements (e.g. the stage-volume curve) |
| `scenario` | "If X happened, here's what would follow" — never a prediction |
| `hypothesis` | An untested idea, explicitly flagged as unproven |
| `recommendation` | A suggested action, not a fact |

**Why this matters for explaining it to anyone:** the system is built so a *guess* can
never visually look like a *measurement*. `core/provenance.py` line 47 (`RENDER_STYLE`)
maps each label to a different way of drawing it on screen — measured, derived, projected,
tentative, advisory. There's even a rule enforced in code (`assert_render_separation`,
line 141) that a `scenario` can never be styled the same as an `observation`.

**`independence_group` — the "is this really two opinions or the same opinion twice"
check.** If two data sources share an `independence_group` (e.g. two AI damage-detection
layers built from the *same* satellite photo), the system treats them as **one** piece of
evidence, not two — because agreeing with yourself isn't confirmation.

---

## Part D — Data filters, summarised

| Filter | What it removes | Where |
|---|---|---|
| **Bounding box** | Everything outside the ~40×80 km corridor | every connector, `bbox` parameter |
| **Cloud-cover ceiling** | Satellite photos too cloudy to read (kept only ≤35% cloud, up to 4 clearest scenes/year) | `/tmp` fetch scripts feeding `core/connectors/stac.py` |
| **Layer selection** | Extra raster bands we don't use | `opera.py` `select_links()` line 74 |
| **`as_of` temporal cutoff** | Any record published *after* the date we claim to be looking from — this is what stops the system from "cheating" by using future information | `core/connectors/base.py`, `as_of_guard()` line 134 |
| **Checksum skip** | Re-downloading a file we already have | `core/connectors/base.py`, `known_checksums()` line 69 |
| **Admin-boundary exclusion** | District/country borders never enter a hazard *scoring* function — they're for display only, because the hazard doesn't respect borders (the source glacier is in China) | design rule, enforced by test in Phase 2 |

---

## Part E — The algorithms actually implemented (deterministic — no AI) — BUILT

**The rule that governs everything here: no AI model is allowed to compute a number.**
Every number below comes from ordinary code doing ordinary maths. An AI model (once built)
is only allowed to *choose which of these to run* and *narrate the result in words* — never
to invent the number itself.

| Algorithm | Plain-English description | Where |
|---|---|---|
| **Windowed raster reading** | Read only a small square out of a huge grid file instead of the whole thing | `analysis/hydro/dem.py` `read_window()` line 59 |
| **Steepest-descent direction** | Look at nearby elevation values and figure out which way water would flow | `analysis/hydro/stage_volume.py` `descent_vector()` line 58 |
| **Synthetic dam construction** | Draw an artificial wall across the valley at the blockage point, to simulate a landslide dam | `stage_volume.py` `build_barrier()` line 75 |
| **Flood-fill / connected-component labelling** | Starting from one point, find every connected pixel that would be underwater at a given water level (classic image-processing algorithm, from `scipy.ndimage`) | `stage_volume.py` `_component_at()` line 90 |
| **Hypsometric integration** | Add up the water volume, one metre of dam height at a time, to build a full curve of "height vs volume" | `stage_volume.py` `_accumulate()` line 138 |
| **Map reprojection** | Convert coordinates from one map projection to another so distances are correct | `core/silver.py` `reproject_raster()` line 30 |
| **Percentile ranking** | Compare one day's rainfall against a full month/year of history to say "this was unusually low/high" | used in `04_precip.ipynb`, plain numpy |
| **SHA-256 checksums** | A fingerprint of a file's exact contents, used to detect if we already have it or if it changed | `core/connectors/base.py` `sha256_of()` line 54 |

None of these are machine learning. They are terrain physics, geometry, and statistics —
the same class of maths a civil engineer would use by hand, just automated.

---

## Part F — The six agents (the AI layer) — PLANNED, not yet built

**Say this plainly when explaining it: none of these six exist as running code yet.**
They are fully designed (see `04-AGENT-REFERENCE.md`), and the data pipeline above is the
foundation they will be built on top of, but as of today there is no LLM in the decision
loop. What follows is the plan, marked clearly.

| # | Agent | One-sentence job | Model | Status |
|---|---|---|---|---|
| 1 | **Scout** | Once a week, glance at all 47 dangerous lakes and decide which ones deserve closer attention | Groq `compound` | 🔲 planned |
| 2 | **Watcher** | Every 15 minutes, cheaply check "did anything change" — almost always says no | Groq `gpt-oss-20b` | 🔲 planned |
| 3 | **Investigator** | Given a goal, decide for itself which calculations to run (from Part E) and in what order, to work out what's happening | Azure `gpt-5.5` | 🔲 planned |
| 4 | **Verifier** | Double-check the Investigator's conclusions using a *different* AI model, and refuse to approve anything the evidence doesn't support | Azure `grok-4.6` | 🔲 planned |
| 5 | **Explainer** | Turn the decision into plain language for the public board and for a WhatsApp message | Groq `gpt-oss-120b` | 🔲 planned |
| 6 | **Actor** | Write the public status automatically (safe) — but for anything more serious, stop and wait for a named human to approve over WhatsApp | Azure `gpt-audio` + deterministic code | 🟡 **partially built** |

**Agent 6 is the one already partly real:** `actions/board.py`, function `write_status()`
(line 21) is the *code half* of the Actor. It writes safe updates automatically, and — this
is the important part — `requires_approval()` (line 17) makes it **impossible in code** for
anything to skip human approval and go straight to a public alert. That safety rule exists
today even though the AI reasoning that would trigger it doesn't yet.

**What's genuinely running today, that looks a bit like an "agent":** `watch/daemon.py`
is a scheduler that wakes up on a timer with no human touching anything, runs the DEM
calculation, and writes a result. It is autonomous (nobody presses a button), but it is
**not intelligent** — it does the exact same calculation every single time, it doesn't
decide anything. That distinction — "runs itself" vs. "decides for itself" — is the honest
line between what's built and what's planned.

---

## Part G — The whole thing in one paragraph, for a non-technical audience

*We download real satellite pictures, elevation maps, population counts, and rainfall
records for one river valley in Nepal. We trim each one down to just our area, convert
them all onto the same map grid, and clean up the parts where the data has holes. Then we
run real physics — not AI — to work out how much water a landslide dam could be holding
back, using the shape of the actual land. That number gets a label attached saying exactly
where it came from and how sure we are. Right now, a timer checks this automatically every
fifteen minutes and posts the result to a public board — safely, because the code
physically cannot post anything more serious than "keep watching" without a named official
approving it first, which we've tested actually works over WhatsApp. The next phase of the
project adds an AI layer on top that reads all this same data and decides for itself what
to investigate — but that AI layer hasn't been written yet.*
