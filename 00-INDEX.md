# SANKET — Document Set

**संकेत** — *the sign that comes before*
National glacial-hazard watch for Nepal · Final set, 3 September 2026

---

## Read in this order

| # | Document | For | Covers |
|---|---|---|---|
| **0** | `00-INDEX.md` | everyone | This page |
| **1** | `01-PRODUCT-SPEC.md` | judges, DHM, NDRRMA, ICIMOD, non-technical readers | What the system is, the problem, how it runs itself, the four preparedness horizons, what you see, what it cannot do |
| **2** | `02-TECHNICAL-SPEC.md` | engineers | Architecture, autonomy engine, six agents, dual-provider gateway, models, datasets, channels, replay, limitations |
| **3** | `03-EVIDENCE-AND-IMPACT.md` | pitch, slides 1, 2 and 7 | The real event record with dates and sources, the science, exposure figures, impact pathways, positioning |
| **4** | `04-AGENT-REFERENCE.md` | engineers, Q&A prep | Each agent's job, model, datasets, communication, boundaries; orchestration; hackathon signal mapping |
| **5** | `05-MASTER-BUILD-PROMPT.md` | the coding agent | Self-contained build instruction, fifteen phases, rules |
| **6** | `06-DATA-AND-AGENTS-PLAIN-ENGLISH.md` | everyone, non-technical | Every dataset and format, cleaning/filtering explained simply, the Evidence envelope, algorithms implemented, agent-by-agent status (built vs planned) |

## Superseded — delete or archive

`SANKET-hackathon-blueprint.md` · `SANKET-fork-map.md` · `SANKET-technical-spec-v2.md` (the early one) · `SANKET-rag-3d-datasets.md` · `SANKET-the-decisions.md` · `SANKET-master-spec.md` · `SANKET-analytics-addendum.md` · `SANKET-standing-watch.md` · `SANKET-national-and-autonomy.md` · `SANKET-agent-reference.md` / `-v2.md` · `SANKET-tech-stack-audit.md` · `SANKET-preparedness-ladder.md` · `SANKET-whatsapp-and-replay.md` · all master build prompts v1–v3 · `1-SANKET-product-spec.md` / `-v2.md` · `2-SANKET-technical-spec.md` / `-v2.md`

Everything in them that survived is in documents 1–5.

---

## The system in six lines

**What.** A national watch over Nepal's glacial-hazard river corridors, designed for DHM and NDRRMA, with District Disaster Management Committees holding the approval gate.

**How it starts.** Nobody starts it. A daemon ticks every fifteen minutes, reacts to new satellite granules published to NASA CMR, and sweeps all 47 potentially dangerous glacial lakes weekly.

**What it does.** Detects impounding water and river blockages, computes what happens downstream and when, adjudicates its own evidence, explains its reasoning, and acts.

**How it acts.** Writes the public board autonomously. Sends Nepali voice, SMS and WhatsApp — with the inundation map attached — only after a named district officer approves, over WhatsApp.

**What it refuses.** It cannot predict a trigger, will not attribute an event to climate change, and issues no claim where credible sources contradict each other.

**Where it is live.** Lhende Khola → Bhotekoshi → Trishuli, Rasuwa and Nuwakot — where a barrier lake formed on 27 August 2026 and is still there.

---

## The six agents

| Agent | Provider | Job |
|---|---|---|
| **Scout** | Groq | Sweeps 47 lakes weekly; decides which corridors deserve close watch |
| **Watcher** | Groq | Ticks; decides whether anything is worth investigating |
| **Investigator** | Azure | Given a goal and twelve tools, works out what happened |
| **Verifier** | Azure | Decides whether the conclusions are supported; can veto |
| **Explainer** | Groq | Attribution, counterfactuals, flip points; three audiences |
| **Actor** | Azure + deterministic | Board, voice, SMS, WhatsApp, the gate |

## The four horizons

| Horizon | Lead time | What it enables |
|---|---|---|
| Standing | permanent | Siren siting, evacuation routes, drill priority |
| Seasonal | weeks–months | Watch-tier promotion, instrument placement |
| **Blockage window** | **hours–days** | **Evacuation. The core of the system.** |
| Propagation | minutes–hours | Downstream alerting by arrival time |
| *Trigger* | *none* | *Not forecastable by anything* |

---

## Honesty commitments — repeat these in every context

- The scenario grid is **precomputed** — caching, as every production geospatial system does. Declared.
- Institutional contact lists are **synthetic**, matching the real distribution, non-routable numbers. Declared.
- The dialler and SMS gateway are **simulated**; the audio and the WhatsApp messages are **real**. Declared.
- In replay mode the **clock is simulated; the data and the agents are real**. Every message prefixed `[REPLAY — TEST]`.
- GeoLibre, the geo-pera solvers, HMAGLOFDB, LiteLLM and every library are listed under **"Brought in"** in the README.
- Casualty figures are provisional and moving. **Every number carries its date.**
- Failed steps stay in the trace.
