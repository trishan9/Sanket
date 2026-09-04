"use client";

import { useEffect, useState } from "react";
import { fetchCascade, fetchDamage, type CascadePayload, type DamagePayload } from "@/lib/risk";

const NODES: readonly [string, ...string[]] = ["lhende_barrier", "purepu_glacier"];
const VOLUMES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0];
const DURATIONS = [5, 15, 30, 60, 120, 180, 360];

export function SimulationControl() {
  const [node, setNode] = useState(NODES[0]);
  const [volume, setVolume] = useState(1.0);
  const [duration, setDuration] = useState(30);
  const [depth, setDepth] = useState(2.0);
  const [cascade, setCascade] = useState<CascadePayload | null>(null);
  const [damage, setDamage] = useState<DamagePayload | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    void fetchCascade(node).then(setCascade);
  }, [node]);

  const run = async () => {
    setRunning(true);
    const [chain, cost] = await Promise.all([
      fetchCascade(node),
      fetchDamage("Syapru Besi", depth, 357, 1),
    ]);
    setCascade(chain);
    setDamage(cost);
    setRunning(false);
  };

  return (
    <section className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Run a scenario
        </h2>
        <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
          SCENARIO
        </span>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-4">
        <label className="text-xs">
          <span className="text-ink-faint">Origin node</span>
          <select
            value={node}
            onChange={(event) => setNode(event.target.value)}
            className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm"
          >
            {NODES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          <span className="text-ink-faint">Volume (Mm³)</span>
          <select
            value={volume}
            onChange={(event) => setVolume(Number(event.target.value))}
            className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm"
          >
            {VOLUMES.map((item) => (
              <option key={item} value={item}>
                {item.toFixed(1)}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          <span className="text-ink-faint">Breach (min)</span>
          <select
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
            className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm"
          >
            {DURATIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs">
          <span className="text-ink-faint">Depth at town (m)</span>
          <input
            type="number"
            step="0.1"
            min="0"
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
            className="mt-1 w-full rounded border border-line bg-surface px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      <button
        onClick={() => void run()}
        disabled={running}
        className="mt-3 rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-[#0a58a8] disabled:opacity-50"
      >
        {running ? "Running…" : `Run ${volume.toFixed(1)} Mm³ / ${duration} min`}
      </button>

      {cascade ? (
        <div className="mt-4 rounded-md border bg-sunken p-3">
          <p className="text-xs text-ink-muted">{cascade.summary}</p>
        </div>
      ) : null}

      {damage ? (
        <div className="mt-2 rounded-md border bg-sunken p-3">
          <p className="text-sm">
            NPR {(damage.low_npr / 1e6).toFixed(1)}-{(damage.high_npr / 1e6).toFixed(1)} million
            <span className="ml-2 text-xs text-ink-faint">
              (USD {(damage.low_usd / 1e6).toFixed(2)}-{(damage.high_usd / 1e6).toFixed(2)}m)
            </span>
          </p>
          <p className="mt-1 text-[11px] text-amber-700">
            Loss of life, injury, displacement and livelihood loss are not monetised.
          </p>
          <ul className="mt-2 space-y-0.5 text-[10px] text-ink-faint">
            {damage.assumptions.slice(0, 4).map((item) => (
              <li key={item}>· {item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
