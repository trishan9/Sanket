"use client";

import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";
const VOLUMES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0];
const DURATIONS = [5, 15, 30, 60, 120, 180, 360];
const BEST_ESTIMATE = { volume: 1.0, duration: 30 };
const UNCERTAINTY_BOX = { minVolume: 0.5, maxVolume: 1.5, minDuration: 15, maxDuration: 60 };

function slugFor(volume: number, duration: number): string {
  return `v${volume.toFixed(1)}_d${duration}_full`;
}

export function ScenarioMatrix() {
  const [available, setAvailable] = useState<Set<string>>(new Set());

  useEffect(() => {
    void fetch(`${BASE}/api/risk/scenarios`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { scenarios: string[] }) => setAvailable(new Set(d.scenarios ?? [])))
      .catch(() => setAvailable(new Set()));
  }, []);

  const inBox = (volume: number, duration: number) =>
    volume >= UNCERTAINTY_BOX.minVolume &&
    volume <= UNCERTAINTY_BOX.maxVolume &&
    duration >= UNCERTAINTY_BOX.minDuration &&
    duration <= UNCERTAINTY_BOX.maxDuration;

  return (
    <section className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Scenario grid, volume × breach duration
        </h2>
        <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
          SCENARIO
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-faint">
        {available.size} precomputed runs. Solid ring is the best estimate; dashed band is the
        uncertainty range we would actually plan against.
      </p>

      <div className="mt-3 overflow-x-auto">
        <table className="text-[11px]">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left text-ink-faint">Mm³ \ min</th>
              {DURATIONS.map((duration) => (
                <th key={duration} className="px-2 py-1 text-ink-faint">
                  {duration}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {VOLUMES.map((volume) => (
              <tr key={volume}>
                <td className="px-2 py-1 text-ink-faint">{volume.toFixed(1)}</td>
                {DURATIONS.map((duration) => {
                  const present = available.has(slugFor(volume, duration));
                  const best =
                    volume === BEST_ESTIMATE.volume && duration === BEST_ESTIMATE.duration;
                  return (
                    <td key={duration} className="px-1 py-1">
                      <div
                        title={`${volume} Mm³ / ${duration} min${present ? "" : " (not computed)"}`}
                        className={`h-7 w-10 rounded ${
                          present ? "bg-[--accent-soft]" : "bg-sunken"
                        } ${best ? "ring-2 ring-accent" : ""} ${
                          inBox(volume, duration) && !best
                            ? "ring-1 ring-dashed ring-amber-500/70"
                            : ""
                        }`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 border-t border-line pt-3 text-[11px] text-ink-faint">
        Every cell is a full 1D Saint-Venant run on the HMA 8 m DEM. A scenario is never rendered
        in the same style as an observation.
      </p>
    </section>
  );
}
