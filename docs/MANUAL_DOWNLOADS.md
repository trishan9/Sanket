# MANUAL_DOWNLOADS — what I need from you

Prepared 3 September 2026 · All URLs below were checked and return a live page today.

Two lists. **Section A is credentials** — I cannot create these, they need your identity or
your card details, and nothing starts without them. **Section B is files** — datasets
behind a registration wall or a portal that has no API, which you need to download and drop
into a named folder.

Everything not on this page, I fetch myself.

**Nothing here changed after the 3 September decisions.** Two open questions closed on my
side without needing you — the GeoLibre project was found on its sharing service, and the
local model lane was dropped — so this list is unchanged and still the critical path.

---

## A · CREDENTIALS — blocking

### A1 · NASA Earthdata login — **the hard blocker, do this first**

**Register:** https://urs.earthdata.nasa.gov/users/new
Free, no card, takes about three minutes.

**Then approve two applications** (Earthdata → Applications → Authorized Apps):
`NSIDC V0 Programmatic Access` and `LP DAAC Data Pool`.

**Give me:** username and password, or write them yourself to `~/.netrc`:

```
machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
```
then `chmod 600 ~/.netrc`. I will use `earthaccess`, which reads that file — you never have
to paste a password into this chat.

**This one gate unlocks, programmatically, with no further downloads from you:**

| Product | CMR short name | Concept ID | Used by |
|---|---|---|---|
| HMA 8 m DEM mosaics | `HMA_DEM8m_MOS` v1 | `C3249536691-NSIDC_CPRD` | Phase 3 — stage–volume, routing, 3D terrain |
| OPERA DSWx-S1 (**the trigger**) | `OPERA_L3_DSWX-S1_V1` | `C2949811996-POCLOUD` | Phases 4, 6, 11 |
| OPERA DIST-ALERT-HLS **v1** | `OPERA_L3_DIST-ALERT-HLS_V1` | `C2746980408-LPCLOUD` | Phases 4, 7 |
| OPERA RTC-S1 | `OPERA_L2_RTC-S1_V1` | `C2777436413-ASF` | Phase 4 radar cross-check |
| GPM IMERG | via GES DISC | — | Phase 4 rainfall rule-out |

Dataset landing page, for reference: https://nsidc.org/data/HMA_DEM8m_MOS/versions/1

> **There is no fallback for the DEM.** Without it there is no stage–volume curve, no
> routing, no arrival times, and no lead times — which is most of the system. Please start
> here.

### A2 · Hackathon Azure endpoint

I need both:
- `HACKATHON_BASE` — the endpoint base URL
- `HACKATHON_KEY` — the API key

Phase 0 runs a live `curl` against `/models` and records **the actual model list** in
`PROGRESS.md`. The brief names `gpt-5.5`, `grok-4.6`, `gpt-audio`, `DeepSeek-V4-Flash` and
`DeepSeek-V4-Pro`; I am treating all five as unverified until that returns. If a name is
wrong, lane assignments change in Phase 0 rather than breaking in Phase 8.

Note: this key is shared by all fifteen teams. The router is built so ~90% of calls land
on Groq for exactly that reason.

### A3 · Groq API key

**Get one:** https://console.groq.com/keys — free tier, no card.
**Give me:** `GROQ_KEY`.

Carries Scout, Watcher Tier 2 and the Explainer — the volume work, on our own quota.

### A4 · Twilio — step by step, since it blocked you

You chose to retry Twilio. Here is the exact path. **No credit card is required for a
trial account** — only a phone verification.

**1. Sign up:** https://www.twilio.com/try-twilio
Email, password, then it sends an SMS code to a phone you control. This verification step
is where most people get stuck: the number you verify with must be able to receive an SMS,
and Twilio rejects some VoIP numbers. Use a normal mobile line.

**2. Skip the onboarding questionnaire.** It asks what you're building; any answer works.
It may offer to buy a number — **you do not need one.** The WhatsApp sandbox uses Twilio's
shared number.

**3. Get the two credentials.** Console home page, "Account Info" panel:
- `Account SID` — starts `AC...`
- `Auth Token` — click to reveal

**4. Open the WhatsApp sandbox.**
Console → **Messaging** → **Try it out** → **Send a WhatsApp message**.
It shows a sandbox number (usually `+1 415 523 8886`) and a join code like `join tiger-blue`.

**5. Join from the phones that will receive messages.** Each recipient sends
`join <your-code>` as a WhatsApp message to that number. That opens a **24-hour
customer-service window** in which free-form text **and media** can be sent with no
template — which is both the opt-in and the mechanism the gate relies on.

I need at least one, ideally two:
1. **The approver** — plays the DDMC Rasuwa duty officer, replies `APPROVE <run_id>`
2. **A resident subscriber** — receives the Nepali message with the inundation map attached

**Then give me:**
```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
APPROVER_WHATSAPP=whatsapp:+977...
```

**Two things to watch, both from the brief:**
- The sandbox number **can be country-restricted**. If a Nepali number never receives the
  join confirmation, that is the blocker — tell me and we switch.
- **Sandbox sessions expire three days after joining.** Whoever joins will need to re-join
  shortly before the demo.

**If it blocks again, tell me the exact step and error.** I am building the messaging layer
behind a single `Channel` interface, so switching to Meta's WhatsApp Cloud API (free, the
brief's own stated production path) or Telegram is a swap of one adapter, not a rewrite —
roughly an hour, not a phase. **Nothing else in the build waits on this.**

### A5 · Optional

- **HuggingFace write token** — only for the Phase 14 dataset publish. Not needed before then.
- **ngrok or Cloudflare Tunnel** — Twilio's inbound webhook needs a public URL to reach the
  Flask route that records approvals. I can set this up; just confirm you are happy for a
  tunnel to expose one local endpoint during the demo.

---

## B · FILES FOR YOU TO DOWNLOAD

Create the folders first:

```bash
mkdir -p data/bronze/manual/{icimod,cems,unosat,msft_damage}
```

### B1 · ICIMOD glacial lake and PDGL inventory — **high priority, Scout depends on it**

**Where:** ICIMOD Regional Database System
- https://doi.org/10.26066/RDS.1971946
- https://doi.org/10.26066/RDS.1971950

Both DOIs resolve. RDS requires a free account and the download is a portal click, so I
cannot script it.

**What I need:** the glacial lake inventory and the **47 potentially dangerous glacial
lakes** across the Koshi, Gandaki and Karnali basins — 21 Nepal, 25 China, 1 India.
Shapefile or GeoPackage preferred, CSV acceptable.

**Drop in:** `data/bronze/manual/icimod/`

Without this, Scout has no population to sweep and Phase 7 cannot meet its exit criteria.
There is no open substitute with the PDGL designation attached.

### B2 · Copernicus EMS EMSR927 — **the validation set for Phase 5 and 14**

**Where:** https://rapidmapping.emergency.copernicus.eu/EMSR927

**What I need:** the vector delineation and grading products, all AOIs, especially the
**Syapru Besi** AOI — the brief cites more than 240 buildings destroyed and 32 damaged,
from WorldView-3 acquired 27/08/2026 05:05 UTC. Shapefile or GeoPackage.

**Drop in:** `data/bronze/manual/cems/`

This is what our modelled inundation gets scored against — confusion matrix, IoU,
precision and recall. Without it, Phase 14 has no validation numbers to publish, and
"we validated against an official product" stops being a claim we can make.

### B3 · UNOSAT mudflow extent, 26–27 August 2026

**Where:** https://www.unosat.org → Maps and Data → Nepal

**What I need:** the flood or mudflow extent product for the Bhotekoshi / Trishuli corridor.

**Drop in:** `data/bronze/manual/unosat/`

Second independent extent. Matters because it gets a **different `independence_group`**
from the CEMS product, which is what lets the Verifier count it as a genuinely separate
line of evidence rather than the same imagery twice.

### B4 · Microsoft AI for Good building damage — *try me first*

**Where:** https://data.humdata.org — search "Nepal flood building damage" or
"AI for Good", August 2026.

I will attempt this through the HDX CKAN API in Phase 1 and it will probably work. Only
if I report it blocked do you need to fetch it by hand.

**Drop in:** `data/bronze/manual/msft_damage/`

Tagged `independence_group: cv_damage_vhr` — the same group as any other computer-vision
damage layer over the same post-event imagery, so the two can never be counted twice.

---

## C · I FETCH THESE MYSELF — no action from you

Verified reachable today: NASA CMR (OPERA catalogue, `updated_since` polling) · Planetary
Computer STAC, anonymous (Sentinel-2 L2A, Sentinel-1 GRD) · HDX CKAN API (`hot_flood_npl`,
`hot_flood_npl_buildings_damage`) · HOT Raw Data API (OSM buildings, roads, bridges,
helipads, health, education, hydropower) · WorldPop 100 m · HMAGLOFDB
(`github.com/fidelsteiner/HMAGLOFDB`, Zenodo 10.5281/zenodo.7271187) · Copernicus DEM
GLO-30 · OCHA COD-AB Nepal ADM2 v02 · Vantor Open Data on S3, no-sign-request
(`10300100C86CED00`, `10500100364E8400`, `B030001100CF1610`) · Planet Crisis Response on
Source Cooperative · USGS ANSS · CHIRPS · the geo-pera reconstruction repo (MIT) · GeoLibre.

**Vantor is confirmed and needs nothing from you.** I listed the bucket: 55 objects under
`events/Nepal-Flooding-Aug-2026/`, anonymous access, all three catalog IDs from the brief
present. Best pre-event scene is `10300100FCB83600` (2024-05-29, 15% cloud); both
post-event scenes are 79% cloud, which is the monsoon-blindness problem the system exists
for and goes on the board rather than being hidden. Streamed as COGs over HTTP range
requests — the 1.4 GB and 1.6 GB scenes are never downloaded whole.

Vantor and Planet are **CC BY-NC 4.0** — anything derived from them lands in a separate
`data/gold/nc/` directory so the clean, reusable layers stay clean.

---

## D · WHAT IS SYNTHETIC — declared here, on the board, and on stage

**Institutional contact lists are invented.** DDMC duty officer, DHM divisional hydrologist,
local administration, hydropower operator, police post, health post, school, community
focal point — matching the real distribution of roles, with **non-routable numbers**. No
real person's contact details enter this system.

The only real numbers anywhere are the two WhatsApp endpoints you supply in A4, which have
opted in by joining the sandbox themselves.

**Also declared:** the dialler and SMS gateway are simulated · the scenario grid is
precomputed, which is caching · in replay mode the clock is simulated.
**Real:** the satellite data, the DEM, the exposure layers, the solver outputs, the Nepali
audio, the WhatsApp messages, and the agents, which run unmodified in replay.

---

## E · ORDER TO DO THIS IN

| | Task | Why now |
|---|---|---|
| 1 | **A1 Earthdata** | Longest lead, blocks the most, no fallback |
| 2 | **A4 Twilio + join the sandbox from a Nepali number** | Country restrictions must surface today, not in Phase 10 |
| 3 | **A2 + A3 keys** | Unblocks Phase 0 immediately |
| 4 | **B1 ICIMOD** | Blocks Phase 7 |
| 5 | **B2 CEMS** | Blocks Phase 14 validation |
| 6 | B3, B4 | Improve the evidence base; not blocking |

**With A2 and A3 alone I can start Phase 0.** A1 is needed before Phase 1.

Paste keys into `.env` at the repo root — it is gitignored from the first commit and
nothing is ever written into a source file.

```
HACKATHON_BASE=
HACKATHON_KEY=
GROQ_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
APPROVER_WHATSAPP=whatsapp:+977...
```
