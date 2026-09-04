"use client";

import { Activity, Banknote, TrendingDown, Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { DEFAULT_LAYERS, HazardMap, type MapLayerState } from "@/components/map/HazardMap";
import { Hero, StatCard, StatRow } from "@/components/shell/Hero";
import { AgentPanel } from "@/components/sim/AgentPanel";
import { fetchCascade, fetchDamage, type CascadePayload, type DamagePayload } from "@/lib/risk";
import { fetchHazard, type HazardPayload } from "@/lib/predict";
import { fetchTrace } from "@/lib/api";
import type { TraceLine } from "@/lib/types";

const VOLUMES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0];
const DURATIONS = [5, 15, 30, 60, 120, 180, 360];
const ORIGIN: [number, number] = [85.377, 28.271];

export default function SimulatePage() {
  const [volume, setVolume] = useState(1.0);
  const [duration, setDuration] = useState(30);
  const [depth, setDepth] = useState(2.4);
  const [buildings, setBuildings] = useState(357);
  const [bridges, setBridges] = useState(1);
  const [dimension, setDimension] = useState<"2d" | "3d">("3d");
  const [layers] = useState<MapLayerState>(DEFAULT_LAYERS);

  const [cascade, setCascade] = useState<CascadePayload | null>(null);
  const [damage, setDamage] = useState<DamagePayload | null>(null);
  const [hazard, setHazard] = useState<HazardPayload | null>(null);
  const [lines, setLines] = useState<TraceLine[]>([]);
  const [running, setRunning] = useState(false);
  const [ranAt, setRanAt] = useState<string | null>(null);

  useEffect(() => {
    void fetchTrace("phase13_both_down_demo").then((payload) => setLines(payload?.lines ?? []));
  }, []);

  const run = async () => {
    setRunning(true);
    const [chain, cost, probability] = await Promise.all([
      fetchCascade("lhende_barrier"),
      fetchDamage("Syapru Besi", depth, buildings, bridges),
      fetchHazard(
        "lhende_barrier",
        {
          seismic_landslide_type: true,
          upstream_mass_movement: true,
          radar_water_anomaly: true,
          antecedent_precip_extreme: false,
        },
        7,
        1,
      ),
    ]);
    setCascade(chain);
    setDamage(cost);
    setHazard(probability);
    setRanAt(new Date().toLocaleTimeString());
    setRunning(false);
  };

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Scenario simulation"
        title="Run a breach and watch the whole system respond"
        lede="Choose a volume and a breach duration, then run it against the real precomputed scenario grid, the cascade graph, the hazard model and the damage bands at once."
        aside={
          <div className="flex items-center gap-2">
            {ranAt ? (
              <span className="chip chip-scenario">SCENARIO · {ranAt}</span>
            ) : null}
            <button onClick={() => void run()} disabled={running} className="btn btn-primary">
              {running ? "Running…" : `Run ${volume.toFixed(1)} Mm³ / ${duration} min`}
            </button>
          </div>
        }
      />

      <StatRow>
        <StatCard
          label="Peak rise at barrier"
          value="6.3 m"
          Icon={Waves}
          tint="red"
          foot="1D Saint-Venant on HMA 8 m DEM"
        />
        <StatCard
          label="Hazard in 7 days"
          value={hazard ? `${(hazard.posterior_probability * 100).toFixed(1)}%` : " "}
          Icon={Activity}
          tint="amber"
          foot={hazard ? `from ${(hazard.prior_probability * 100).toFixed(1)}% prior` : "run to compute"}
        />
        <StatCard
          label="Chain confidence at end"
          value={cascade ? cascade.terminal_confidence.toFixed(2) : " "}
          Icon={TrendingDown}
          tint="blue"
          foot={cascade ? `${cascade.steps.length} nodes, ×${cascade.decay_per_step} decay` : "run to compute"}
        />
        <StatCard
          label="Direct asset damage"
          value={
            damage
              ? `${(damage.low_npr / 1e6).toFixed(0)}-${(damage.high_npr / 1e6).toFixed(0)}M`
              : " "
          }
          Icon={Banknote}
          tint="slate"
          foot="NPR range, life not monetised"
        />
      </StatRow>

      <div className="mt-4 grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="card">
          <div className="border-b px-4 py-3">
            <span className="card-title">Breach parameters</span>
          </div>
          <div className="space-y-4 px-4 py-4">
            <label className="block">
              <span className="label">Impounded volume</span>
              <select
                value={volume}
                onChange={(event) => setVolume(Number(event.target.value))}
                className="field mt-1.5"
              >
                {VOLUMES.map((item) => (
                  <option key={item} value={item}>
                    {item.toFixed(1)} Mm³
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Breach duration</span>
              <select
                value={duration}
                onChange={(event) => setDuration(Number(event.target.value))}
                className="field mt-1.5"
              >
                {DURATIONS.map((item) => (
                  <option key={item} value={item}>
                    {item} min
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Depth at town (m)</span>
              <input
                type="number"
                step="0.1"
                min="0"
                value={depth}
                onChange={(event) => setDepth(Number(event.target.value))}
                className="field mt-1.5"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="label">Buildings</span>
                <input
                  type="number"
                  value={buildings}
                  onChange={(event) => setBuildings(Number(event.target.value))}
                  className="field mt-1.5"
                />
              </label>
              <label className="block">
                <span className="label">Bridges</span>
                <input
                  type="number"
                  value={bridges}
                  onChange={(event) => setBridges(Number(event.target.value))}
                  className="field mt-1.5"
                />
              </label>
            </div>
            <div>
              <span className="label">View</span>
              <div className="mt-1.5 grid grid-cols-2 gap-1 rounded-md border p-1">
                {(["2d", "3d"] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setDimension(mode)}
                    className={`rounded px-2 py-1.5 text-[12px] font-medium ${
                      dimension === mode ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                    }`}
                  >
                    {mode.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <HazardMap layers={layers} dimension={dimension} focus={ORIGIN} height={520} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <AgentPanel lines={lines} />

        <section className="card overflow-hidden">
          <div className="card-head">
            <span className="card-title">Consequence</span>
            <span className="chip chip-scenario">SCENARIO</span>
          </div>
          {cascade ? (
            <ol className="px-5 py-4">
              {cascade.steps.map((step) => (
                <li key={step.node_id} className="flex items-center gap-3 py-1.5">
                  <span className="w-36 shrink-0 truncate text-[12.5px] font-medium">
                    {step.node_id}
                  </span>
                  <div className="h-2 flex-1 overflow-hidden rounded bg-sunken">
                    <div
                      className="h-full rounded bg-accent"
                      style={{ width: `${Math.max(4, step.confidence * 100)}%` }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right font-mono text-[12px] text-ink-muted">
                    {step.confidence.toFixed(2)}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="px-5 py-10 text-center text-[13px] text-ink-muted">
              Run a scenario to populate the chain.
            </p>
          )}
          {damage ? (
            <div className="card-note">
              <div className="font-mono text-[13px] text-ink">
                NPR {(damage.low_npr / 1e6).toFixed(1)}-{(damage.high_npr / 1e6).toFixed(1)} million
                <span className="ml-2 text-ink-faint">
                  (USD {(damage.low_usd / 1e6).toFixed(2)}-{(damage.high_usd / 1e6).toFixed(2)}m)
                </span>
              </div>
              <p className="mt-1.5">
                Loss of life, injury, displacement and livelihood loss are not monetised.
              </p>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
