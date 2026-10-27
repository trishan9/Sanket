# 01 — SANKET Product Specification

**संकेत** — *the sign that comes before*
Non-technical · For judges, DHM, NDRRMA, ICIMOD, and anyone who needs to understand this without reading code

---

## 1. In one sentence

**SANKET helps Nepal's disaster authorities warn communities below glacial lakes without anyone watching a screen.**

It is a national watch that runs itself. Nobody logs in. Nobody types a question. It looks, it decides, it explains, and it acts.

---

## 2. The problem

### What happened

On the morning of **26 August 2026**, a mass of glacier ice and rock roughly six hundred metres across broke away from about 5,600 metres on the Langtang Himal, on the Nepal–Tibet border, and fell into the upper Lhende Khola. The United States Geological Survey first catalogued it as a magnitude 4.4 earthquake, then reclassified it as a **magnitude 5.2 landslide event** — the ground shook *because* the mountain fell, not the other way around.

The debris dammed the river. The dam failed. The surge travelled down the Lhende into the Bhotekoshi, then the Trishuli, which rose by as much as **nine metres in thirty minutes**. Bodies were recovered across seven districts — Rasuwa, Nuwakot, Dhading, Gorkha, Tanahun, Chitwan and both Nawalparasi districts.

Casualty figures moved daily and remain provisional. Reported recoveries passed 900 by the end of August, with several thousand still missing. More than ten hydropower projects were damaged.

Thirteen months earlier, on **8 July 2025**, the same river system flooded from a glacial lake outburst in Jilong County, Tibet. The Miteri Bridge — the Nepal–China Friendship Bridge — was destroyed.

**Neither event was caused by rain.**

### Why nothing saw it coming

**The source is in another country.** Nepal has no gauges in the upper Lhende and no automatic feed from it. When the critical satellite imagery reached DHM after the 2026 event, it came *through Chinese authorities*, not through any standing arrangement.

**Every early-warning system Nepal operates is anchored to rainfall.** Rain gauges trigger alerts; river gauges sit downstream of settlements. A dry-day ice collapse in Tibet is invisible to all of it by design.

**It is monsoon season.** Optical satellites see cloud, not ground, for much of the year. Radar sees through cloud, but almost nobody is using it for this.

**Small lakes kill people.** The lake that failed at Thame in 2024 was roughly the size of five football pitches. Conventional inventories do not reliably track objects that small.

### The scale

ICIMOD counts **more than 25,000 glacial lakes** across the Hindu Kush Himalaya. The ICIMOD/UNDP assessment identified **47 potentially dangerous glacial lakes** across Nepal's Koshi, Gandaki and Karnali basins — **21 in Nepal, 25 in China, one in India.** Twenty-five of the lakes that threaten Nepali settlements sit on the other side of a border.

Every one of the 47 sits above a river corridor with settlements, roads, bridges and hydropower on it. **Not one is under continuous automated watch today.**

### The fact that made us build this

ICIMOD researchers analysed the satellite record for this catchment and found a lake at the Purepu Glacier, about thirty-five kilometres upstream of the Nepal border, that:

- **formed and drained within about a week in July 2023**, sending a flood ten kilometres downstream
- **widened again in December 2024**
- **grew significantly in June 2025** — weeks before the July 2025 outburst

Three years of visible warning, in a river system that then flooded catastrophically twice. Every image was free, public, and available the day it was taken.

The gap was never data. Nobody was looking, continuously, at all of it.

### And it is not over

The August 2026 collapse left a **barrier lake** — water impounded behind the debris. China's Ministry of Water Resources estimated it at **one and a half to two million cubic metres**, with up to three million more possibly flowing in over three days. It began overflowing on 28 August and rescue operations stopped.

**That lake is still there.**

---

## 3. What SANKET is

A **national glacial-hazard watch**, designed to be operated by the **Department of Hydrology and Meteorology** and **NDRRMA**, with **District Disaster Management Committees** holding the approval authority for their own districts.

**The architecture is national. One corridor runs at high cadence; all 47 are swept weekly.**

A corridor is a small configuration file — its bounding box, the features it watches, the settlements below it, the terrain model it uses, and which authority holds the gate. Adding a corridor is a data operation, not a rebuild. The Lhende–Bhotekoshi–Trishuli corridor runs live because it is the most active glacial-hazard corridor in Nepal. Thame in Solukhumbu and Tilgau in Humla are ready to follow, and both have published records to check the system against.

---

## 4. How it runs itself

### It is a watch, not an app

A background process that never stops. No login page, no search box. Once started, nothing human is required for it to do its job.

### Watching is deliberately cheap

Every fifteen minutes it asks three questions, using no AI at all:

- Has a new satellite image been published over any watched valley since the last check?
- Has any river gauge we can reach crossed its threshold?
- Is anything we are already tracking due for another look?

Almost always the answer is no to all three. It writes a heartbeat and sleeps. This costs essentially nothing.

### It reacts to publication, not to a schedule

The system does not know when a satellite will pass overhead, and does not need to. NASA publishes each new radar-derived water map as soon as it is processed, and SANKET checks that catalogue every tick. **The moment new evidence exists is the moment it looks** — the only sensible definition of watching.

### It escalates in steps

A new image arrives. The system measures water and disturbance in the watched valley against a baseline **it computed itself** from the previous fortnight. Within normal variation? Update the baseline, sleep. Most images end here.

Outside normal? A small, fast model asks one question: is this a real physical change, a sensor artefact, or seasonal variation? Radar shadows in steep valleys and melting snow both look like change and are not. Catching those cheaply is what stops the expensive path firing on noise.

Only if that comes back *real* does the full investigation begin.

**Watching is free. Deciding is cheap. Investigating is expensive — and investigating is rare.**

### It decides where to look, nationally

Once a week it sweeps all 47 potentially dangerous glacial lakes and **decides for itself which corridors deserve closer attention**. A basin with an active anomaly gets checked every fifteen minutes; one with an elevated signal every six hours; the rest weekly. The system allocates its own attention across the country — that is what makes it a national watch rather than one valley with a camera on it.

### The investigation

It is given a goal, not a checklist: *characterise what changed, determine whether water is being impounded, and if so work out the consequence downstream and how confident you are.* It then chooses its own steps.

Different situations genuinely produce different investigations. New water at a known lake leads it through the lake's multi-year history, a rainfall check, past events in the same basin, then how much water the valley holds, what happens when it fails, where the flood goes, and who is in the way. A disturbance with no water signature leads it to check the terrain, find no impoundment, and stop — nothing to model. An ambiguous signal under heavy cloud leads it to conclude the evidence is insufficient and hand over to a person rather than manufacture an answer.

### Then it checks its own work

A separate stage, running on a **different AI model from the one that did the reasoning**, examines every conclusion. It lists the evidence for and against, checks whether the supporting sources are genuinely independent of one another, and assigns a confidence level. Where the evidence does not support a conclusion, it refuses to issue one.

A model checking its own work is not a check.

### Then it explains

Before anything reaches a human, another stage makes the decision legible. Not a summary — an explanation:

- **What drove this**, and by how much: change magnitude, lead time, exposed population, confidence
- **What would have to be different**: *"at one and a half million cubic metres instead of two and a half, Timure gets twenty-six minutes instead of fourteen, and this is not an alert"*
- **The flip point**: the exact value at which the answer changes
- **What would change its mind** — including which open questions are irrelevant to the decision

### Then it acts

At **Watch** level it acts alone: writes the status, the public board changes, DHM's duty channel is notified. Nobody pressed anything and something changed in the world.

At **Alert** level everything stops. It prepares the call list, generates the Nepali audio, drafts the messages, assembles the evidence — and waits for a named district officer to approve.

### It remembers

Between runs it knows what it flagged, who it contacted, and what normal looks like in each valley, because it worked that out itself. The second run behaves differently from the first: it recognises an anomaly it is already tracking rather than opening a new one, does not re-contact a settlement it reached forty minutes ago, and if something has grown for three consecutive checks, that trend itself becomes evidence.

### It does not cry wolf

Raising the status requires crossing a higher bar than staying there, so it does not flicker. A settlement is not re-contacted inside a cooldown window unless things get worse. The same physical event seen in three consecutive images is one event with three observations, not three alarms.

---

## 5. The four horizons

The most common question about a system like this is *"how early?"* There are four honest answers, and one place where the answer is *not at all*.

| Horizon | What is detected | Lead time | What it enables |
|---|---|---|---|
| **Standing** | Who lives below which lake; terrain; modelled flood under a full range of scenarios | permanent | Siren siting, evacuation route design, assembly points, drill priority |
| **Seasonal** | Repeated lake formation, growth trend, disturbance accumulation | weeks–months | Pre-monsoon briefing, instrument placement, watch-tier promotion |
| **Blockage window** | A river has been dammed and water is impounding | **hours–days** | Evacuation, road closure, hydropower shutdown |
| **Propagation** | A surge is already moving downstream | minutes–hours | Downstream alerting, in arrival-time order |

### Standing preparedness — available today, before anything happens

For every corridor the system already holds the answer to *"if the worst plausible thing happens here, what does it look like and who is in the way?"* — computed once, standing ready.

| A district officer asks | The system answers |
|---|---|
| Where do we put a siren? | Settlements with the shortest modelled lead time and largest exposed population |
| Which bridge is a single point of failure? | The ones whose loss isolates a settlement under most scenarios |
| Where do people go? | Mapped assembly points above modelled peak stage, with routes |
| Which ward do we drill first? | Highest exposure, shortest lead time, weakest egress |

**This is disaster risk reduction, not disaster response.** It requires no alert to be useful, and it is the part that saves the most lives per rupee.

### The blockage window — the core of the system

When a landslide or avalanche dams a river, there is a window between the blockage **forming** and **failing**. On the Lhende in August 2026 that window was **more than a day** — the barrier lake formed on the 27th and began overflowing on the 28th.

It is detectable because impounded water is one of the clearest signals radar produces, it works through cloud, the volume is computable from terrain, and **the consequence is already precomputed**. A blockage detected at 09:12 produces arrival times for every downstream settlement at 09:12, not after two hours of modelling.

The constraint, stated honestly: detection is bounded by satellite revisit — roughly six to twelve days for radar over Nepal, plus processing time. A blockage that forms and fails inside a single gap will be missed. That is a concrete, fundable argument for more frequent acquisition over Nepal's high corridors.

### The horizon where we deliver nothing

**We cannot predict the trigger.** Six hundred metres of ice detaching at 5,600 metres was not forecastable, by us or anyone. Trigger processes are stochastic and operate below the scale any satellite resolves.

**But because everything downstream of a trigger is precomputed and standing ready, the response to an unpredictable event collapses from hours of scrambling to seconds of dissemination.** The exposure is known, the routes are drawn, the arrival times are in the grid, the call list is assembled.

> **The mountain is not predictable. The consequence is.**

---

## 6. What you see, and what arrives

### The board — public, always on, Nepali

It does not wait for anyone to look at it, because the system already looked, decided, explained and wrote the status.

- **Corridor and per-settlement status**, each with arrival time under the current scenario and a confidence marker
- **When it was last checked**, and how old the newest evidence is — always visible
- **A three-dimensional view of the valley**, with a swipe handle between real before and after satellite imagery, and the system's own modelled flood extent drawn over what was actually observed
- **What the agent found**, in plain language, including anything it refused to conclude and why
- **Why it says that** — what drove the decision, what would change it, where it flips
- **Four charts**: the lake's area over a decade with cloudy periods shaded so you can see where nobody could see; rainfall against twenty years of history, showing that rain explains nothing; how many people have under thirty minutes of warning; and the system's own run history
- **The national picture** — 47 basins swept, when, and which are being watched closely
- **What this run cost**, in rupees

On a slow connection it degrades to a four-kilobyte text page with the same information, in Nepali, that renders on an old handset.

**And a Preparedness view, available when nothing is happening** — the scenario-range flood extent, lead-time distribution, isolation risk and assembly points for any settlement. This is the view a district officer opens on an ordinary Tuesday.

### What arrives on a phone

For people downstream the product is not a screen.

- **A Nepali voice call**, about twenty seconds, naming their settlement and how long they have
- **An SMS**, 140 characters, for any handset
- **A WhatsApp message** carrying the thing the other two cannot: **the flood map itself**, alongside the arrival time and a link to the full evidence

Nobody is contacted without opting in.

### And for the officer who has to decide

The approval request goes to the district duty officer **as a WhatsApp message** — because at three in the morning they have a phone, not a laptop. It contains what drove the decision, what would have to be different, the before-and-after image, and a reply-to-approve instruction.

A decision you cannot interrogate is a rubber stamp. This one you can.

---

## 7. The human checkpoint

**SANKET will never make a phone call, send a message, or raise a public warning without a named district officer approving it.**

Below that line it acts on its own: writing the board, logging reasoning, marking confidence. Above it, everything stops at a gate.

We drew the line there on purpose. A false flood warning empties a valley, disrupts livelihoods, and burns the trust that the next real warning depends on. Board updates are reversible and cheap; a warning is neither. That cost is not the machine's to bear.

---

## 8. The principle that governs everything

**The system is built to be unable to present a guess as a measurement.**

Every piece of information carries a label — **observation**, **correlation**, **model output**, **scenario**, **hypothesis**, **recommendation**. A scenario never looks like an observation on the screen, enforced in the software rather than left to whoever writes the caption.

### What it will never claim

- **It cannot predict an outburst or an avalanche.** No system can, and we say so.
- **It will not attribute any single flood to climate change.** It will report that a measurement exceeded its historical range. That is where the sentence stops.
- **It will not claim these floods are becoming more frequent.** The scientific literature genuinely disagrees. What *is* well supported is that lakes are growing and far more people live below them — so **exposure** has increased, which is a different and more useful statement.

---

## 9. The honesty test it is currently passing

The cause of the August 2026 flood is contested right now, by credible parties. DHM and ICIMOD concluded from satellite imagery that it was an outburst from a supraglacial lake in Tibet. An independent reconstruction from open satellite data concluded that no pre-existing lake drained at all — and publicly retracted one of its own key figures after finding an error in its method.

**SANKET does not pick a side.** It records that two credible sources disagree, notes that one has already corrected itself, checks whether they are genuinely independent — if both worked from the same imagery, they are one line of evidence, not two — and **issues no conclusion** on the cause.

Then it says the thing that is still useful: *the mechanism is uncertain, and the assessment of who is downstream and how long they have does not depend on which explanation is right.*

Every dashboard we have looked at would have printed a number there.

---

## 10. The bad day

> It is the last week of August. The monsoon has not lifted for eleven days — every optical satellite pass returns cloud. The road is cut in three places. Mains power in Dhunche has been out for fourteen hours and the district office is on a generator with intermittent 2G. The AI service is unreachable because a submarine cable is down. And at 08:37 a mountain falls into the river.
>
> SANKET does not stop. Radar sees through cloud, so blockage detection still runs. It falls back to a second provider, then to a small model running on the machine in the district office, and records that it did. The flood calculation is arithmetic on a terrain model already on disk. The board degrades to a four-kilobyte page that renders over 2G. The phone call goes out over the cellular voice network, which survives when data does not. Every output is stamped with how old its newest evidence is.
>
> What it will not do is guess. If the evidence is ambiguous and confidence falls below threshold, it says so, hands over to a person, and does not manufacture a warning it cannot support.

---

## 11. Who it is for

| | |
|---|---|
| **DHM, Flood Forecasting Division** | National operator. Already runs a 24/7 monsoon service and the 1155 line. Their forecasting is rainfall-anchored — this is the channel they do not have. |
| **NDRRMA** | Owns the national response mandate and the BIPAD platform. SANKET's status records write into the same picture BIPAD holds. |
| **District Disaster Management Committees** | Hold the approval gate. Seventy-seven exist. The gate sits with the district because the district bears the cost of a false warning. |
| **ICIMOD** | Scientific authority on the lake inventory and cryosphere monitoring. SANKET operationalises science they already publish. |
| **Local government and the public** | Status, voice, SMS, WhatsApp. No expertise required, no login, works on an old handset. |

---

## 12. What it cannot do

**It cannot predict the trigger.** What this provides is preparedness, not prophecy.

**Terrain models are out of date the moment a flood passes.** The valley has been reshaped by an enormous volume of debris, and every calculation made on pre-event terrain is wrong in ways we cannot correct without new survey.

**Cloud and revisit gaps are real.** A lake can form and drain entirely between two satellite passes — apparently what happened at Purepu in July 2023.

**We cannot see all the dangerous lakes.** The imagery cannot reliably detect water below about three thousand square metres. Some of the lakes that will matter next are smaller.

**Population figures are modelled, not counted.** They estimate where people usually live and cannot show who has been displaced.

**The source catchment is in China.** No ground data, no gauges, no guaranteed imagery sharing. A diplomatic problem, not a technical one, and no software fixes it.

**Every warning needs human confirmation.** This is decision support. The decision to evacuate belongs to local authority.

---

## 13. What is genuinely new

**Nobody is watching these valleys.** Not because the data is missing — it is free and public — but because nothing was assembling it continuously. SANKET is a standing watch where there was none.

**A system that refuses.** Not a confidence percentage bolted onto an answer, but a separate stage with the authority to say *insufficient evidence, no conclusion issued* — and an independence check that stops the same source counting twice. It is currently passing a live, unplanned test on the contested attribution of a disaster that happened last week.

**Explanation the approver can interrogate.** Not a score, but what drove the decision, what would have to be different, and which open questions do not matter.

**Watching blockages, not just lakes.** Existing hazard work monitors lakes. Both events that killed people here involved a river blockage forming and failing — temporary, detectable by radar within days, measurable from terrain, with hours of genuinely usable warning time.

**Built to run in Nepal, on Nepali data, depending on nobody.** Free satellite data, open models, two independent AI providers with automatic failover, a local fallback so it works with the network unplugged, and public institutions as the natural owners. **This should be public infrastructure, not a business** — and every input is already public.

---

## 14. The closing thought

Nepal already has the data. Climate records, disaster records, satellite archives anyone can download, terrain models, population figures, and a glacial lake inventory compiled by an institute headquartered in Kathmandu.

What Nepal has never had is something looking at all of it, all the time, and honest about the parts it cannot answer.

Most days SANKET will do nothing visible. That is correct. A board reading *checked four minutes ago, nothing has changed, newest evidence six hours old* is a national watch doing its job.

**The value is not in the alerts. It is in the continuous, dated, honest absence of them — and in the fact that when something does change, nobody had to be looking.**
