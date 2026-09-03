# 08 — UPDATE PROMPT: RISK ENGINE

**Give this to the agent after the main build is under way. It is additive. Nothing already built should change behaviour.**

---

## CONTEXT

You have built, or are building, SANKET per `05-MASTER-BUILD-PROMPT.md`: a six-agent autonomous watch with a daemon, a bounded tool loop, a verifier with veto, an explainer, a board, and WhatsApp/voice/SMS alerting behind a human gate.

This update adds a **risk engine** on top. The full design is in `07-RISK-ENGINE-IMPLEMENTATION.md` — read it before starting.

---

## THE RULE THAT GOVERNS THIS UPDATE

**Additive only. Do not refactor working code.**

- New modules in new files. Existing modules gain new functions, not rewritten ones.
- Existing tests must pass **unchanged** at every step. If one breaks, you have modified behaviour — stop and revert.
- New tools are appended to the tool registry. **The existing twelve keep their exact signatures.**
- New alert levels extend the existing ladder; `NORMAL`, `WATCH`, `ALERT`, `INSUFFICIENT` keep working during the transition.
- New dashboard routes are added. Existing routes keep rendering.
- **Every rule in Part K of the master prompt still applies**, plus eight new ones at the end of this document.

**Before you start:** run the full test suite and record the pass count in `PROGRESS.md`. That number is your regression baseline. It may only go up.

---

## FIRST ACTION

1. Read `07-RISK-ENGINE-IMPLEMENTATION.md` in full. Part 1 governs every claim the rest may make.
2. Append to `PLAN.md` a section **"Risk engine — additive plan"** covering: the five sub-phases below, new file paths, new dependencies, what you will touch in existing files and why it is safe, and your regression baseline.
3. List anything you believe would require changing existing behaviour, and **ask before doing it.**
4. **Stop and wait for approval.**

Then work through the sub-phases in order, stopping after each.

---

## THE PRINCIPLE THIS UPDATE ENFORCES

> **We predict consequence, not occurrence.**

Three separate outputs, only one of which is a prediction:

| Output | Type | Basis |
|---|---|---|
| **Susceptibility** | a **ranking**, never a probability | Published parameter frameworks (Rounce et al. 2016 HESS 20:3455; ICIMOD/UNDP 2020 PDGL methodology) + empirical base rates from HMAGLOFDB's 697 recorded events |
| **State change** | **detection**, not prediction | Statistical anomaly against a self-computed baseline |
| **Consequence** | **prediction**, and validatable | Shallow-water routing over the HMA 8 m DEM, checked against Copernicus EMS EMSR927 |

**No output anywhere may state or imply that a specific lake will fail, or when.** A test must assert this across every rendered string.

---

## SUB-PHASE A — Risk engine core

**New files**

```
analysis/risk/
  susceptibility.py     parameter extraction + scoring + base rates
  base_rates.py         HMAGLOFDB empirical rates with CIs and sample sizes
  cascade_graph.py      hazard nodes on the drainage network
  cascade_sim.py        chain simulation with confidence decay
  observability.py      detection limits, "not observable" ≠ "not present"
  schemas.py            HazardNode, SusceptibilityScore, CascadeResult
```

**Susceptibility parameters** — implement the parameter set, cite the frameworks, **do not invent thresholds**:

| Group | Parameters |
|---|---|
| Dam | type (moraine / ice / bedrock / landslide-debris) · freeboard · width-to-height ratio · ice core present · outlet condition |
| Lake | area · change rate · expansion direction relative to glacier · glacier-terminus contact · volume via published area–volume scaling |
| Trigger potential | slope above the lake · recent mass movement · avalanche-prone terrain above · seismic history |
| Conditioning | temperature anomaly · antecedent rainfall · snowmelt season |
| Downstream | channel gradient · valley confinement · distance to first settlement · exposed population |

**Base rates, not invented weights.** Join HMAGLOFDB (lakes that failed) against the ICIMOD inventory (lakes that did not), compute the empirical rate per parameter, report with a confidence interval **and the sample size beside it.**

**Cascade graph.** Every water body and blockage is a node on the flow-accumulation network. Node types **must include non-glacial hazards** — `landslide_dam`, `debris_dam`, `barrier_lake`, `reservoir`, `confluence`. A landslide dam is mathematically the same object as a moraine dam, and it is what killed people on the Bhotekoshi twice.

**Confidence decays along the chain.** A three-step cascade cannot carry the confidence of a single-step one, and the decay must be visible in the output.

**Observability.** Two thresholds: the detection limit (~0.003 km², below which we genuinely cannot distinguish a lake from noise) and a much lower attention threshold. The Thame lake was ~0.05 km². Every susceptibility output carries a statement of what is below the limit and therefore unknown.

**New tools** appended to the registry: `susceptibility_at(node_id)` · `cascade_from(node_id, breach)` · `observability_report(catchment)`

**Exit criteria**
- All 47 PDGLs scored and ranked
- Base rates reported with CIs and sample sizes
- **A test asserts no output string contains a probability of failure or a failure date**
- Cascade simulation runs a three-node chain with visibly decaying confidence
- Regression baseline unchanged

---

## SUB-PHASE B — Meteorological integration

**New files**

```
analysis/met/
  percentile.py        rainfall vs 20-year climatology
  anomaly.py           temperature, freezing level, antecedent wetness
  ruleout.py           rainfall_explains()
```

**The rule-out is the point.** On both 8 July 2025 and 26 August 2026 basin rainfall was unremarkable. That negative result is what proves the hazard is cryospheric and therefore invisible to every rainfall-threshold system Nepal operates.

Temperature is a **conditioning factor, not a trigger** — the peer-reviewed Thame reconstruction links a temperature spike to the tipping point, but does not make it causal on its own. Weight accordingly.

**New tool:** `met_context(basin, date)` returning percentile, anomalies, and a plain-language read.

**Exit criteria**
- `rainfall_explains()` returns `explains=False` for both event dates
- Met strip renders on both dashboards
- Regression baseline unchanged

---

## SUB-PHASE C — Multi-level alerts and damage

**New files**

```
actions/levels.py                five-level ladder, per-zone
analysis/economics/damage.py     depth-damage functions, ranges
```

**Five levels:** `GREEN` · `YELLOW` · `ORANGE` · `RED` · `GREY`. **GREY means "cannot assess"** — stale evidence, cloud-blocked, or contradictory — and it is an honest state, not a failure.

**Per settlement, not per corridor.** Timure can be RED while Betrawati is ORANGE in the same event at the same moment.

**Migration:** map existing `NORMAL→GREEN`, `WATCH→YELLOW`, `ALERT→RED`, `INSUFFICIENT→GREY`. Keep the old names accepted as aliases so nothing already written breaks. `ORANGE` is new.

**Hysteresis, cooldown, and one-way-within-event** all carry over from the existing ladder.

**Damage estimates are ranges with assumptions listed.** Never point estimates. Every figure carries the statement that loss of life, injury, displacement and livelihood loss are **not monetised** — which are the real costs.

**Exit criteria**
- Different settlements hold different levels simultaneously in one event
- Old level names still resolve
- Damage output emits ranges with cited unit-cost sources and listed assumptions
- **A test asserts no point-estimate damage figure is ever produced**
- Regression baseline unchanged

---

## SUB-PHASE D — Flash-flood fast path

**New file:** `watch/flash.py`

Rate-of-change detection rather than level: stage rate over 30 minutes, rainfall intensity over 60 minutes, **USGS ANSS landslide-type events in-basin**, and sudden large DIST-ALERT disturbance.

**The seismic path matters specifically.** USGS reclassified the 26 August signal from an M4.4 earthquake to an **M5.2 landslide-type event** — the shaking was caused by the collapse. A landslide-type event inside a watched basin is a strong, near-instant, independent indicator. **Poll ANSS every tick.**

**The fast path bypasses normal escalation:** skip Tier 2 classification, run a reduced Investigator with `MAX_STEPS = 4` doing exposure and arrival time only, jump to ORANGE or RED, gate with a short deadline and an auto-escalation contact, suppress cooldown for this event.

**It never sends without approval** — but if a RED flash gate is unanswered by its deadline it escalates to the next named contact and logs it, rather than waiting silently on one person's phone.

**Labelled as a fast path everywhere**, with its own reduced-confidence tier, because it is running on less evidence by design.

**Exit criteria**
- A simulated stage-rate spike reaches a gate request in under 60 seconds
- A landslide-type seismic event in-basin triggers the fast path
- The fast path is labelled in the trace, on the board and in every message
- Auto-escalation fires on deadline and is logged
- Regression baseline unchanged

---

## SUB-PHASE E — Dashboards

**New routes:** `/gov` (authenticated, technical) and the public `/` extended.

**New components**

```
board/app/gov/                    technical dashboard
board/components/risk/
  CascadeGraph.tsx                interactive node-link, confidence decay visible
  SusceptibilityPanel.tsx         47 PDGLs ranked, with base rates and CIs
  ScenarioMatrix.tsx              volume × breach, best estimate + uncertainty box
  ValidationPanel.tsx             confusion matrix vs EMSR927, calibration residuals
  CompletenessHeatmap.tsx         usable scenes by month, optical vs radar
board/components/awareness/
  CausalGraph.tsx                 cited edges, strength labels, attribution banner
  MeasuresPanel.tsx               tiered by who can act
board/components/sim/
  SimulationControl.tsx           choose node, volume, breach, run
  AgentPanel.tsx                  six agents lighting up in sequence
  AmISafe.tsx                     settlement lookup → zone, lead time, assembly point
```

**The causal graph is the delicate one.** Nodes are documented drivers, edges carry citations and strength labels (`established` / `supported` / `contested` / `local observation`).

**One edge must be labelled `contested`:** *warming → more frequent GLOFs.* Veh et al. (2019, Nature Climate Change) found **unchanged** frequency of moraine-dammed GLOFs in the Himalaya, and HMAGLOFDB describes the evidence as ambiguous. What *is* supported is that lakes are growing and far more people live below them — exposure has increased.

**Every view of that panel carries a persistent banner:**

> These are documented general mechanisms in the scientific literature. They are not an attribution of any specific flood. Attributing a single event requires dedicated attribution study, which we have not done.

**3D requirements:** risk-zone heatmap with two independent dropdowns — height by one variable, colour by another. **Height = exposure, colour = confidence** produces tall grey columns meaning *places we think are at risk and are not sure about.* That is the picture nobody else can draw.

**Exit criteria**
- Every capability implemented in A–D is visible somewhere in one of the two dashboards
- Causal graph carries the banner on every view
- **A test asserts no rendered string attributes a specific event to a specific cause**
- Public dashboard loads under 2 s throttled
- Existing routes render unchanged
- Regression baseline unchanged

---

## NEW RULES — append to Part K

**22.** Susceptibility output is a **ranking**, never a probability of failure. No output may state or imply that a specific lake will fail, or when.

**23.** Every base rate carries a confidence interval and a sample size.

**24.** Below the detection limit, report **"not observable"** — never "not present."

**25.** The causal-graph panel carries the non-attribution banner on every view. No rendered string may attribute a specific event to a specific cause.

**26.** Economic figures are **ranges** with assumptions listed and unit-cost sources cited. Never point estimates. Always accompanied by the statement that loss of life is not monetised.

**27.** Cascade confidence decays with chain length, and the decay is displayed.

**28.** The flash path is labelled as such in the trace, on the board and in every message, and carries its own reduced-confidence tier.

**29.** Simulation and replay outputs are watermarked `SCENARIO` or `REPLAY` and can never be styled like an observation.

---

## REGRESSION GATE — check at every sub-phase boundary

1. Full test suite passes with **at least** the baseline count
2. `mypy --strict` clean on `core/` and `analysis/`
3. `ruff` clean, **zero comments** in any source file
4. The daemon still starts and ticks unattended
5. Tiers 0 and 1 still make **zero LLM calls**
6. The existing twelve tools have unchanged signatures
7. An investigation still runs end to end
8. The gate still holds
9. WhatsApp, voice and SMS still send
10. Replay still runs

**If any of these fail, stop. Do not proceed to the next sub-phase.**

---

## START

Append the risk-engine plan to `PLAN.md`, record your regression baseline, list anything that would require changing existing behaviour, and **stop for approval.**
