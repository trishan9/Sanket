"use client";

import {
  Binary,
  BrainCircuit,
  Database,
  Gauge,
  Layers3,
  Radio,
  Ruler,
  Satellite,
  ShieldCheck,
  Siren,
  Waves,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Hero, Section } from "@/components/shell/Hero";

interface Stage {
  Icon: LucideIcon;
  tint: string;
  step: string;
  title: string;
  body: string;
  detail: string[];
}

const STAGES: Stage[] = [
  {
    Icon: Satellite,
    tint: "bg-sky-50 text-sky-600 border-sky-200",
    step: "01",
    title: "Pixels arrive as radiance, not as answers",
    body:
      "Every input starts as a raster granule. OPERA DSWx-S1 gives a water-classification band derived from Sentinel-1 radar backscatter, OPERA DIST-ALERT-HLS gives a vegetation-disturbance status band from Harmonised Landsat Sentinel optical reflectance, and Sentinel-2 L2A gives raw surface reflectance in green and shortwave-infrared. None of these is a number this system can reason about yet.",
    detail: [
      "granules are fetched by NASA CMR search against the corridor bounding box and stored with a checksum manifest",
      "each file keeps its acquisition timestamp, which later becomes the temporal firewall",
    ],
  },
  {
    Icon: Binary,
    tint: "bg-violet-50 text-violet-600 border-violet-200",
    step: "02",
    title: "Images become a single number per scene",
    body:
      "A raster is reduced to one scalar so it can be compared across time. For DSWx the open-water and partial-water classes are counted and multiplied by pixel area to give square kilometres of water. For Sentinel-2 the green and shortwave bands are combined into MNDWI, then a bounded Otsu threshold separates water from land and the same area sum is taken. For DIST-ALERT the confirmed-disturbance classes are counted the same way.",
    detail: [
      "water_area_km2 = count(class in open, partial) x pixel_area_m2 / 1e6",
      "MNDWI = (green - swir) / (green + swir), thresholded per scene rather than with a fixed cut",
      "cloud-obscured scenes are flagged and excluded rather than silently averaged in",
    ],
  },
  {
    Icon: Gauge,
    tint: "bg-amber-50 text-amber-600 border-amber-200",
    step: "03",
    title: "A number becomes an anomaly only against its own history",
    body:
      "One area measurement means nothing on its own. The system keeps a rolling baseline of the last fourteen observations for each product and tile, computes mean and variance, and scores the newest observation as a z-score. Only a z at or beyond three counts as a step change worth escalating. This is Tier 0 and Tier 1, and it makes zero model calls.",
    detail: [
      "baseline is self-computed from this system's own history, not a published threshold",
      "the same machinery runs on radar, so it keeps working through monsoon cloud",
      "a within-band observation refreshes the baseline, so the detector adapts to seasonality",
    ],
  },
  {
    Icon: Ruler,
    tint: "bg-emerald-50 text-emerald-600 border-emerald-200",
    step: "04",
    title: "Terrain turns an anomaly into a volume and a travel time",
    body:
      "The HMA 8 m DEM is read as a window around the blockage. A dam of stated crest height is imposed across the channel, water is filled upstream eight-connected until it spills, and the result is a stage-volume curve in real cubic metres. That volume drives a parametric breach hydrograph, which is routed down 314 extracted cross-sections by a 1D Saint-Venant solver using a Rusanov flux, producing arrival time and peak stage rise at each settlement.",
    detail: [
      "stage-volume, breach and routing are deterministic Python; no model ever computes a number",
      "56 volume-by-duration combinations are precomputed so a live run is a lookup, not a solve",
      "WorldPop and OSM footprints are intersected with the wet cells to count who is inside",
    ],
  },
  {
    Icon: Database,
    tint: "bg-slate-100 text-ink-soft border-line",
    step: "05",
    title: "Independent datasets are joined to make base rates",
    body:
      "HMAGLOFDB holds 773 recorded outburst events since 1833. The ICIMOD 2015 inventory holds 3,624 mapped glacial lakes. Joining events against inventory by dam type produces an empirical rate per lake: moraine 390 events across 2,002 lakes, ice 344 across 339, bedrock 6 across 1,256. That last join is what turns a literature claim into a measured prior with a confidence interval and a sample size beside it.",
    detail: [
      "ice-dammed lakes exceed one event per lake because they drain repeatedly, so a Poisson interval is used rather than a binomial one",
      "CHIRPS supplies a 21-year same-month climatology so rainfall can be ruled in or out",
      "USGS ANSS supplies event type, which is how a landslide-type signal is separated from an earthquake",
    ],
  },
  {
    Icon: BrainCircuit,
    tint: "bg-red-50 text-red-600 border-red-200",
    step: "06",
    title: "Six agents reason over the numbers, never over the pixels",
    body:
      "Scout sweeps all 47 potentially dangerous lakes weekly and sets how often each corridor is looked at. Watcher runs the zero-model detector and classifies a step change. Investigator opens a bounded ReAct loop, choosing its own sequence over twelve deterministic tools with a hard ten-step limit. Verifier checks every claim for independence, temporal validity, evidence licensing and contradiction against retrieved literature, and can veto. Explainer turns the surviving claims into a decision with contributions and counterfactuals. Actor writes the board below WATCH, or stops at the gate above it.",
    detail: [
      "the model picks which function to call and how to read the result, it never produces a figure",
      "every call goes through one router with Azure to Groq failover and a deterministic fourth rung",
      "the sandbox that answers free-form questions is read-only and cannot touch a status or a gate",
    ],
  },
  {
    Icon: Waves,
    tint: "bg-orange-50 text-orange-600 border-orange-200",
    step: "07",
    title: "Prediction is a Bayesian update, not a score",
    body:
      "The measured base rate becomes a per-lake-year Poisson prior, widened by an under-reporting factor because the documentary record is incomplete. For a dam that has already formed the inventory rate is the wrong question, so the prior switches to the Costa and Schuster survival curve conditioned on days already survived. Six indicators then multiply the prior odds by cited likelihood ratios. Anything the sensors could not see multiplies by exactly one and is named in the output.",
    detail: [
      "a landslide-type seismic event carries the heaviest ratio because it is the mechanism that operated here",
      "20,000 Monte Carlo draws over prior uncertainty give the credible interval",
      "the output is a probability for a lake of that class carrying those indicators, never a date",
    ],
  },
  {
    Icon: Siren,
    tint: "bg-amber-50 text-amber-600 border-amber-200",
    step: "08",
    title: "One event produces several messages, not one verdict",
    body:
      "A single unexplained step change goes out immediately as a GREY advisory, autonomously, because it asks for attention rather than action. When a second independent line of evidence agrees or the hazard estimate crosses the corroboration threshold it becomes ORANGE and stops at the district gate. Only after the Verifier accepts does it become RED. If the evidence disappears the system publishes a GREEN stand-down as loudly as it escalated, and a Verifier veto drops the whole thing back to an advisory.",
    detail: [
      "the advisory sits below the autonomous ceiling by design, which is why it can be instant",
      "each resident settlement receives its own card with its own level, lead time and language",
      "an unanswered RED gate escalates to the next named contact on a deadline and is logged",
    ],
  },
];

const DATASETS = [
  { name: "OPERA DSWx-S1", kind: "radar raster", use: "water extent through cloud", vintage: "rolling" },
  { name: "OPERA DIST-ALERT-HLS", kind: "optical raster", use: "surface disturbance above the lake", vintage: "rolling" },
  { name: "Sentinel-1 RTC", kind: "radar backscatter", use: "Tier 0 detection at the barrier", vintage: "rolling" },
  { name: "Sentinel-2 L2A", kind: "optical reflectance", use: "MNDWI lake-area time series", vintage: "2016 to 2026" },
  { name: "HMA 8 m DEM", kind: "elevation raster", use: "stage-volume, cross-sections, routing", vintage: "2017-07-16" },
  { name: "CHIRPS v2.0", kind: "gridded rainfall", use: "percentile against 21-year climatology", vintage: "2006 to 2026" },
  { name: "HMAGLOFDB", kind: "event table", use: "empirical base rates by dam type", vintage: "1833 to 2022" },
  { name: "ICIMOD inventory", kind: "lake polygons", use: "denominator for base rates, 47 PDGLs", vintage: "2015" },
  { name: "WorldPop", kind: "population raster", use: "people inside the wet cells", vintage: "2020" },
  { name: "OSM and HOT", kind: "vector footprints", use: "buildings and bridges exposed", vintage: "rolling" },
  { name: "USGS ANSS", kind: "event catalogue", use: "landslide-type seismic trigger", vintage: "rolling" },
  { name: "CEMS EMSR927", kind: "observed extent", use: "validation reference", vintage: "2026-08" },
];

export default function PipelinePage() {
  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="How the system actually works"
        title="From raw satellite pixels to a warning someone can act on"
        lede="The full chain, in order: what each dataset physically is, how an image becomes a number, how that number becomes an anomaly, how terrain turns it into arrival time, and where the agents and the alert ladder sit on top."
      />

      <div className="card mb-4 px-6 py-5">
        <div className="label">In one paragraph</div>
        <p className="mt-2 max-w-none text-[14.5px] leading-[1.75] text-ink-soft">
          SANKET ingests free satellite rasters and reduces each scene to a single physical
          number: radar and optical water bands are class-counted and multiplied by pixel area to
          give square kilometres of water, Sentinel-2 green and shortwave bands are combined into
          MNDWI and thresholded per scene, and disturbance classes are counted the same way. Those
          scalars are meaningless alone, so each is scored as a z-score against a rolling
          fourteen-observation baseline the system computed itself, which is the entire Tier 0 and
          Tier 1 detector and makes zero model calls. When a step change survives that test, the
          8 m DEM is used to impose a dam at the blockage, fill upstream until spill, and read off
          a real stage-volume curve; that volume drives a parametric breach hydrograph routed
          through 314 extracted cross-sections by a 1D Saint-Venant solver, giving arrival time and
          peak rise per settlement, which is then intersected with WorldPop and OSM footprints to
          count who and what is inside. In parallel, joining 773 HMAGLOFDB events against 3,624
          ICIMOD inventory lakes by dam type produces measured base rates with intervals and sample
          sizes, and CHIRPS, USGS ANSS event types and the literature supply the conditioning
          evidence. Only at this point do the six agents engage, and they reason strictly over
          those numbers rather than the imagery: Scout allocates attention nationally, Watcher
          classifies the anomaly, Investigator runs a bounded ten-step loop choosing its own path
          through twelve deterministic tools, Verifier checks independence, timing, licensing and
          contradiction and can veto outright, Explainer converts surviving claims into a decision
          with contributions and counterfactuals, and Actor either writes the public board or stops
          at the district gate. The prediction layer turns the base rate into a Poisson prior,
          swaps to a Costa and Schuster survival prior when a dam has already formed, and multiplies
          by cited likelihood ratios for each observed indicator while anything unobserved
          multiplies by exactly one, producing a probability with a Monte Carlo credible interval
          rather than a single confident figure. That probability then drives a ladder rather than a
          verdict: a lone unexplained change is broadcast within seconds as a GREY advisory with no
          human in the loop, corroboration by a second independent line lifts it to ORANGE at the
          gate, Verifier acceptance lifts it to RED, disappearing evidence publishes a GREEN
          stand-down, and a veto drops it back to an advisory, so the system can warn early and be
          wrong safely instead of staying silent until it is certain.
        </p>
      </div>

      <div className="space-y-3">
        {STAGES.map((stage) => (
          <div key={stage.step} className="card px-6 py-5">
            <div className="flex flex-wrap items-start gap-5">
              <span
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${stage.tint}`}
              >
                <stage.Icon size={20} strokeWidth={1.9} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[12px] font-semibold text-ink-faint">
                    {stage.step}
                  </span>
                  <h2 className="text-[17px] font-semibold tracking-[-0.01em]">{stage.title}</h2>
                </div>
                <p className="mt-2 max-w-4xl text-[13.5px] leading-relaxed text-ink-soft">
                  {stage.body}
                </p>
                <ul className="mt-3 grid gap-1.5 lg:grid-cols-3">
                  {stage.detail.map((item) => (
                    <li
                      key={item}
                      className="rounded-md border bg-sunken px-3 py-2 font-mono text-[11px] leading-snug text-ink-muted"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <Section
          eyebrow="Inputs"
          title="Every dataset, what it physically is, and what it is used for"
          aside={
            <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-faint">
              <Layers3 size={13} /> {DATASETS.length} sources
            </span>
          }
          note="Nothing here is synthetic. Where a layer is not held at all, such as air temperature, the system reports it as unobserved rather than assuming it is normal."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12.5px]">
              <thead className="bg-sunken">
                <tr>
                  <th className="px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Dataset
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Physical form
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Role in the chain
                  </th>
                  <th className="px-5 py-2 text-right text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Vintage
                  </th>
                </tr>
              </thead>
              <tbody>
                {DATASETS.map((row) => (
                  <tr key={row.name} className="border-b last:border-0">
                    <td className="px-5 py-2.5 font-medium">{row.name}</td>
                    <td className="px-3 py-2.5 text-ink-muted">{row.kind}</td>
                    <td className="px-3 py-2.5 text-ink-soft">{row.use}</td>
                    <td className="px-5 py-2.5 text-right font-mono text-[11px] text-ink-faint">
                      {row.vintage}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          eyebrow="Guardrails"
          title="What the design refuses to do"
          note="These are enforced by tests in the build, not by prompt instructions."
        >
          <ul className="space-y-2.5 px-5 py-4">
            {[
              { Icon: Radio, text: "No human input path exists to start a run. The daemon triggers itself." },
              { Icon: Ruler, text: "The model never computes a number. Every figure comes from deterministic Python." },
              { Icon: ShieldCheck, text: "Nothing above WATCH is released without recorded approval from a named district officer." },
              { Icon: Gauge, text: "A scenario is never rendered in the same visual style as an observation." },
              { Icon: Database, text: "Below the detection limit the answer is not observable, never not present." },
              { Icon: BrainCircuit, text: "Susceptibility is a ranking. No output states that a lake will fail, or when." },
            ].map((item) => (
              <li key={item.text} className="flex gap-3">
                <item.Icon size={15} className="mt-0.5 shrink-0 text-ink-faint" strokeWidth={1.9} />
                <span className="text-[12.5px] leading-relaxed text-ink-soft">{item.text}</span>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </main>
  );
}
