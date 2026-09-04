"use client";

import { useState } from "react";

type Actor = "household" | "ward" | "district" | "national";

interface Measure {
  actor: Actor;
  title: string;
  detail: string;
  horizon: string;
}

const ACTOR_LABEL: Record<Actor, string> = {
  household: "Household",
  ward: "Ward / community",
  district: "District (DDMC)",
  national: "National (DHM / NDRRMA)",
};

const MEASURES: Measure[] = [
  {
    actor: "household",
    title: "Know your high ground and the route to it",
    detail:
      "Lead times on this corridor are minutes, not hours. The decision that matters is made " +
      "before the alert arrives, not after.",
    horizon: "now",
  },
  {
    actor: "household",
    title: "Opt in to alerts and keep a charged handset",
    detail: "Send START to the SANKET number. Send STOP at any time to leave.",
    horizon: "now",
  },
  {
    actor: "ward",
    title: "Mark and sign assembly points above the modelled reach",
    detail:
      "Assembly points must sit above the highest modelled stage rise, with a margin for the " +
      "debris load a water-only model does not capture.",
    horizon: "weeks",
  },
  {
    actor: "ward",
    title: "Run a timed evacuation drill against the real lead time",
    detail: "A drill that takes longer than the modelled arrival time is the finding, not a failure.",
    horizon: "weeks",
  },
  {
    actor: "district",
    title: "Hold the approval gate and keep the duty roster current",
    detail:
      "No alert leaves this system without a named district officer approving it. An unstaffed " +
      "gate is an unusable system.",
    horizon: "continuous",
  },
  {
    actor: "district",
    title: "Pre-position for isolation, not just inundation",
    detail:
      "Bridge loss cuts settlements off long after the water drops. Single points of failure are " +
      "listed on the preparedness view.",
    horizon: "months",
  },
  {
    actor: "national",
    title: "Fund radar-first monitoring for cryospheric hazard",
    detail:
      "Every operational early-warning channel in Nepal is anchored to rainfall. Both events on " +
      "this river happened on unremarkable rainfall days.",
    horizon: "years",
  },
  {
    actor: "national",
    title: "Negotiate transboundary data sharing for the source catchment",
    detail:
      "Twenty-five of the 47 potentially dangerous lakes sit across the border. This is a " +
      "diplomatic problem, not a technical one.",
    horizon: "years",
  },
];

export function MeasuresPanel() {
  const [actor, setActor] = useState<Actor | "all">("all");
  const shown = actor === "all" ? MEASURES : MEASURES.filter((m) => m.actor === actor);

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        What can actually be done
      </h2>
      <p className="mt-1 text-xs text-ink-faint">Tiered by who has the authority to act.</p>

      <div className="mt-3 flex flex-wrap gap-1">
        {(["all", "household", "ward", "district", "national"] as const).map((key) => (
          <button
            key={key}
            onClick={() => setActor(key)}
            className={`rounded px-2 py-1 text-[11px] ${
              actor === key
                ? "bg-accent text-white"
                : "bg-[--surface-sunken] text-ink-muted hover:bg-sunken"
            }`}
          >
            {key === "all" ? "All" : ACTOR_LABEL[key]}
          </button>
        ))}
      </div>

      <ul className="mt-3 space-y-2">
        {shown.map((measure) => (
          <li key={measure.title} className="rounded-md border bg-sunken p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-[--surface-sunken] px-2 py-0.5 text-[10px] uppercase tracking-wide text-ink-muted">
                {ACTOR_LABEL[measure.actor]}
              </span>
              <span className="text-sm font-medium">{measure.title}</span>
              <span className="ml-auto text-[10px] text-ink-faint">{measure.horizon}</span>
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-ink-muted">{measure.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
