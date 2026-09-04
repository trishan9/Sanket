"use client";

import { useEffect, useState } from "react";
import { fetchSusceptibility, type SusceptibilityScore } from "@/lib/risk";

const BAND_COLOR: Record<string, string> = {
  very_high: "bg-red-50 text-red-800",
  high: "bg-orange-50 text-orange-800",
  moderate: "bg-amber-50 text-amber-800",
  low: "bg-[--surface-sunken] text-ink-muted",
  not_assessable: "bg-[--surface-sunken] text-ink-faint",
};

export function SusceptibilityPanel() {
  const [scores, setScores] = useState<SusceptibilityScore[]>([]);
  const [selected, setSelected] = useState<SusceptibilityScore | null>(null);

  useEffect(() => {
    void fetchSusceptibility().then((data) => {
      if (data) {
        setScores(data.ranked);
        setSelected(data.ranked[0] ?? null);
      }
    });
  }, []);

  if (scores.length === 0) {
    return (
      <section className="card card-pad">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Susceptibility ranking
        </h2>
        <p className="mt-2 text-sm text-ink-muted">Loading ranked lakes…</p>
      </section>
    );
  }

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Susceptibility ranking, {scores.length} potentially dangerous glacial lakes
      </h2>
      <p className="mt-1 text-xs text-amber-700">
        A ranking against other inventoried lakes. Not a probability of failure, and never a
        statement of when any lake may fail.
      </p>

      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <ol className="max-h-80 space-y-1 overflow-y-auto pr-1">
          {scores.map((score, index) => (
            <li key={score.node_id}>
              <button
                onClick={() => setSelected(score)}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-sunken ${
                  selected?.node_id === score.node_id ? "bg-[--surface-sunken]" : ""
                }`}
              >
                <span className="w-6 shrink-0 text-ink-faint">{index + 1}</span>
                <span className="flex-1 truncate font-mono">{score.node_id}</span>
                <span className="w-28 shrink-0">
                  <span className="block h-1.5 overflow-hidden rounded bg-[--surface-sunken]">
                    <span
                      className="block h-full bg-accent"
                      style={{ width: `${Math.round(score.rank_score * 100)}%` }}
                    />
                  </span>
                </span>
                <span className="w-10 shrink-0 text-right font-mono text-ink-soft">
                  {score.rank_score.toFixed(2)}
                </span>
              </button>
            </li>
          ))}
        </ol>

        {selected ? (
          <div className="rounded-md border bg-sunken p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm">{selected.node_id}</span>
              <span
                className={`rounded px-2 py-0.5 text-[11px] font-semibold uppercase ${
                  BAND_COLOR[selected.band] ?? BAND_COLOR.low
                }`}
              >
                {selected.band.replace(/_/g, " ")}
              </span>
            </div>

            {selected.base_rates.map((rate) => (
              <p key={rate.stratum} className="mt-2 text-[11px] text-ink-muted">
                {rate.rendered}
              </p>
            ))}

            <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
              Observed parameters
            </h3>
            <ul className="mt-1 space-y-0.5 text-[11px] text-ink-muted">
              {selected.parameters
                .filter((p) => p.observable && p.value !== null)
                .map((p) => (
                  <li key={p.name}>
                    {p.name}: {p.value?.toFixed(3)} <span className="text-ink-faint">{p.note}</span>
                  </li>
                ))}
            </ul>

            <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-amber-700">
              Not observable, excluded, not assumed benign
            </h3>
            <p className="mt-1 text-[11px] text-ink-faint">
              {selected.unobservable_parameters.join(", ")}
            </p>

            <h3 className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
              Frameworks
            </h3>
            <ul className="mt-1 space-y-0.5 text-[11px] text-ink-faint">
              {selected.frameworks.map((framework) => (
                <li key={framework}>· {framework}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
