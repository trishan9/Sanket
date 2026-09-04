# SANKET (संकेत) — Solution Sheet

## One sentence

**SANKET helps Nepal's disaster authorities warn communities below glacial lakes without anyone watching a screen** — a national standing watch that looks, decides, explains and acts on its own, and stops at a named human before anything reaches the public.

## Named user

**The DDMC Rasuwa Duty Officer** — the district disaster management committee official who holds the approval gate for the Bhotekoshi–Trishuli corridor. Every gated action (voice call, SMS, WhatsApp, any public status above `WATCH`) is addressed to this named role, by identity, over WhatsApp, and recorded with a timestamp when approved or rejected. `core/contacts.py::Approver` is the only non-synthetic contact in the system — a real number, verified with a real Twilio WhatsApp delivery (see git history, "Verify Twilio WhatsApp delivery to a Nepali number").

## What the agent does unasked

Nobody logs in and nobody types a question. On a schedule, with zero human input to start a run, SANKET: pulls new OPERA/Sentinel granules and CHIRPS rainfall; runs a two-tier, zero-LLM change detector against a self-computed rolling baseline; classifies a real anomaly; runs an open ReAct investigation (Investigator chooses its own tool sequence, up to 10 steps, over 12 deterministic Python tools — never a hardcoded chain); verifies every claim against independence, temporal, licensing and contradiction checks with veto power; explains the decision (contributions, counterfactuals, flip points, "what would change my mind", in English and Nepali); and **autonomously writes the public board at `NORMAL`/`WATCH`** — no human touches this path. Only above `WATCH` does it stop and ask.

## Architecture

```
 Scout (weekly, all 47 PDGLs)         Watcher (Tier 0/1 zero-LLM, Tier 2 classify)
        |                                        |
        v                                        v
  basin_tiers -----------------------------> handoff -> work_queue
                                                          |
                                                          v
                                                    Investigator
                                          (ReAct loop, 12 deterministic tools,
                                           MAX_STEPS=10, Azure -> Groq failover)
                                                          |
                                                          v
                                                      Verifier
                                     (independence / temporal / licensing / contradiction,
                                      veto authority; degrades gracefully, never blocks)
                                                          |
                                                          v
                                                     Explainer
                                (deterministic decide(); public note EN/NE; evidence pack)
                                                          |
                                                          v
                                                        Actor
                                    <= WATCH: autonomous board write (core.board.write_status)
                                    >  WATCH: WhatsApp gate request -> named district officer
                                                          |
                                     approved -> voice (real TTS) + SMS + WhatsApp to residents
```

No provider SDK is imported outside `agent/router.py` (enforced by an import-linter contract and an AST test). Deterministic mode — a fourth rung below Azure and Groq — runs the same 12 tools in a fixed sequence when no LLM is reachable at all; the decision function itself (`agent/decision.py::decide()`) is pure Python in every rung, per the rule that the LLM never computes a number.

## Tools and models

**Models:** Azure `gpt-5.5` (Investigator), Azure `grok-4.6` (Verifier), Groq `gpt-oss-120b` (Explainer), Groq `compound` (Scout), Groq `gpt-oss-20b` (Watcher Tier 2 classify), Azure `gpt-audio` (voice TTS) — routed through a single LiteLLM `Router` with per-lane Azure↔Groq fallback, all behind `agent/router.py::gateway`.

**The Investigator's 12 tools** (the same 12 exposed by `sanket-mcp`): `search_granules`, `detect_water_change`, `detect_disturbance`, `lake_area_series`, `precip_percentile`, `stage_volume`, `breach_hydrograph`, `route_flood`, `exposure_at`, `precedent`, `science_lookup`, `write_status`. Every one is deterministic Python — DEM hypsometric fill, a parametric breach hydrograph, a 1D Saint-Venant / Rusanov-flux router, MNDWI water detection, a rolling-baseline z-score classifier. The model chooses which to call, in what order, with what arguments; it never computes a number itself.

## The human checkpoint

**SANKET will never make a phone call, send a message, or raise a public warning without the DDMC Rasuwa Duty Officer approving it.** Below `WATCH` it acts on its own — writing the board, logging reasoning, marking confidence. Above that line, everything stops at a gate: the approval request goes out over WhatsApp with the full Explainer pack (what drove the decision, what would flip it, the before/after image), and only a recorded, identity-stamped reply from the registered approver releases it. Enforced in code (`core/board.py::requires_approval`), not left to a prompt.

## The bad day

It is the last week of August. The monsoon has not lifted for eleven days — every optical satellite pass returns cloud. The road is cut in three places. Mains power in Dhunche has been out for fourteen hours and the district office is on a generator with intermittent 2G. The AI service is unreachable because a submarine cable is down. And at 08:37 a mountain falls into the river.

SANKET does not stop. Radar sees through cloud, so blockage detection still runs. The Investigator's own Azure lane fails over to Groq automatically; when both fail, deterministic mode runs the same 12 tools in a fixed sequence and still produces a `WATCH` decision with a full evidence pack — verified live this build, five `DEGRADED` trace lines and a real autonomous board write, no LLM involved. The flood calculation is arithmetic on a terrain model already on disk. The board degrades to a 448-byte page that renders instantly over a throttled connection. A status written before the outage is still served, its age shown in hours. What it will not do is guess: if the evidence is ambiguous, the Verifier vetoes and the Explainer says so in plain language, in both languages, rather than manufacturing a warning it cannot support.

## Blunt real-vs-mocked list

**Real:** every satellite/EO product (OPERA DSWx-S1, DIST-ALERT-HLS, Sentinel-1 RTC, Sentinel-2 L2A), CHIRPS rainfall, the HMA 8 m DEM, WorldPop, OSM/HOT, HMAGLOFDB, the ICIMOD glacial-lake inventory · the DEM stage-volume curve, breach hydrograph and 1D Saint-Venant flood router (real physics, calibrated against an independent reconstruction, with an honestly reported -83% residual and a stated reason why) · the LiteLLM Azure↔Groq router and its failover, including deterministic mode, all verified live this session by actually invalidating keys at runtime · Verifier's independence/temporal/licensing/contradiction checks and RAG grounding · WhatsApp delivery to the district officer, via Twilio, verified live to a real Nepali number · voice TTS audio (Azure `gpt-audio`, real synthesis) · the gate's identity-and-timestamp approval record · the MCP server's 12 real tool schemas, callable by an external client.

**Synthetic, declared:** the institutional contact table (hydropower operator, police post, health post, school, community focal point — non-routable numbers; the DDMC approver's own contact is the one real one) · SMS sending (`actions/sms.py::SIMULATED_GATEWAY`, no real carrier send) · the voice call's phone dial-out (`VoiceCallResult.dialler_simulated=True` — the audio is real, the outbound call is not) · the replay clock (elapsed time only — every granule, DEM read, exposure count and solver output it drives is real, per rule 21) · the precomputed scenario grid (real solver output, but a `scenario`, never rendered as an `observation`) · the `sanket-plan-local` Ollama rung, which was evaluated and **dropped**, not shipped as unrunnable config, because this machine's 7 GB RAM / 4 GB VRAM cannot run `gpt-oss-20b`'s 13–16 GB requirement · the shared Azure key and (for this build's automated verification only) the Groq key were exercised via invalid-key injection rather than a real console revocation — the live demo revokes the real Groq key, since it is this team's own.

## What it cannot do

It cannot predict the trigger — this is preparedness, not prophecy. Terrain models are out of date the moment a flood passes; every scenario computed on pre-event terrain is wrong in ways that cannot be corrected without new survey. Cloud and revisit gaps are real — a lake can form and drain entirely between two satellite passes, as apparently happened at Purepu in July 2023. Population figures are modelled, not counted. The source catchment is in China — no ground gauges, no guaranteed imagery sharing, a diplomatic problem no software fixes. Every warning still needs human confirmation; the decision to evacuate belongs to local authority, not to SANKET.
