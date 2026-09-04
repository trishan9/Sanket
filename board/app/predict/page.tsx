"use client";

import { Activity, Circle, SlidersHorizontal, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { IndicatorBoard } from "@/components/predict/IndicatorBoard";
import { Hero, StatCard, StatRow } from "@/components/shell/Hero";
import {
  fetchHazard,
  fetchIndicators,
  type HazardPayload,
  type IndicatorSpec,
  type Observations,
} from "@/lib/predict";

const NODES = ["lhende_barrier", "purepu_glacier"];
const WINDOWS = [1, 3, 7, 14, 30];

function pct(value: number): string {
  if (value >= 0.1) return `${(value * 100).toFixed(1)}%`;
  if (value >= 0.001) return `${(value * 100).toFixed(2)}%`;
  return `${(value * 100).toExponential(1)}%`;
}

export default function PredictPage() {
  const [indicators, setIndicators] = useState<IndicatorSpec[]>([]);
  const [observations, setObservations] = useState<Observations>({});
  const [node, setNode] = useState(NODES[0] as string);
  const [windowDays, setWindowDays] = useState(7);
  const [daysSince, setDaysSince] = useState(1);
  const [hazard, setHazard] = useState<HazardPayload | null>(null);

  useEffect(() => {
    void fetchIndicators().then((data) => setIndicators(data?.indicators ?? []));
  }, []);

  useEffect(() => {
    void fetchHazard(node, observations, windowDays, daysSince).then(setHazard);
  }, [node, observations, windowDays, daysSince]);

  const ordered = useMemo(() => {
    if (!hazard) return [];
    return [...hazard.readings]
      .filter((r) => r.state !== "not observed")
      .sort((a, b) => Math.abs(b.log_contribution) - Math.abs(a.log_contribution));
  }, [hazard]);

  const maxAbs = Math.max(0.01, ...ordered.map((r) => Math.abs(r.log_contribution)));

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Probabilistic hazard model"
        title="How likely, over what window, and what moved the number"
        lede="A Bayesian update on an empirical base rate. Every likelihood ratio is cited, and anything the sensors could not see contributes nothing at all."
      />

      {hazard ? (
        <StatRow>
          <StatCard
            label="Posterior probability"
            value={pct(hazard.posterior_probability)}
            Icon={Activity}
            tint="red"
            foot={`in ${hazard.window_days} days`}
          />
          <StatCard
            label="Base rate before evidence"
            value={pct(hazard.prior_probability)}
            Icon={Circle}
            tint="slate"
            foot={`${hazard.dam_type}-dammed prior`}
          />
          <StatCard
            label="Evidence lift"
            value={`${hazard.lift >= 100 ? hazard.lift.toFixed(0) : hazard.lift.toFixed(2)}×`}
            Icon={TrendingUp}
            tint="amber"
            foot="posterior ÷ prior"
          />
          <StatCard
            label="90% credible interval"
            value={`${pct(hazard.credible_interval[0])} to ${pct(hazard.credible_interval[1])}`}
            Icon={SlidersHorizontal}
            tint="blue"
            foot="Monte Carlo over prior uncertainty"
          />
        </StatRow>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-[300px_1fr]">
        <aside className="card">
          <div className="border-b px-4 py-3">
            <span className="card-title">Scenario</span>
          </div>
          <div className="space-y-4 px-4 py-4">
            <label className="block">
              <span className="label">Node</span>
              <select
                value={node}
                onChange={(event) => setNode(event.target.value)}
                className="field mt-1.5"
              >
                {NODES.map((item) => (
                  <option key={item} value={item}>
                    {item.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="label">Window</span>
              <div className="mt-1.5 grid grid-cols-5 gap-1 rounded-md border p-1">
                {WINDOWS.map((item) => (
                  <button
                    key={item}
                    onClick={() => setWindowDays(item)}
                    className={`rounded py-1.5 text-[12px] font-medium ${
                      windowDays === item ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                    }`}
                  >
                    {item}d
                  </button>
                ))}
              </div>
            </label>
            <label className="block">
              <span className="label">Days since the dam formed</span>
              <input
                type="range"
                min={0}
                max={120}
                value={daysSince}
                onChange={(event) => setDaysSince(Number(event.target.value))}
                className="mt-2 w-full accent-[--accent]"
              />
              <div className="mt-1 flex justify-between text-[11px] text-ink-faint">
                <span>fresh</span>
                <span className="font-mono text-ink-soft">{daysSince} d</span>
                <span>120 d</span>
              </div>
            </label>
          </div>
        </aside>

        <IndicatorBoard
          indicators={indicators}
          observations={observations}
          onChange={setObservations}
        />
      </div>

      {hazard ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <section className="card overflow-hidden">
            <div className="card-head">
              <span className="card-title">What moved the number</span>
              <span className="text-[11px] text-ink-faint">log likelihood ratio</span>
            </div>
            <div className="px-5 py-4">
              {ordered.length === 0 ? (
                <p className="text-[13px] text-ink-muted">
                  Nothing observed yet, the estimate is the bare base rate.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {ordered.map((reading) => {
                    const positive = reading.log_contribution >= 0;
                    const width = (Math.abs(reading.log_contribution) / maxAbs) * 50;
                    return (
                      <li key={reading.key} className="text-[12px]">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{reading.key.replace(/_/g, " ")}</span>
                          <span className="font-mono text-ink-muted">
                            {reading.likelihood_ratio}× {reading.state}
                          </span>
                        </div>
                        <div className="relative mt-1 h-3 rounded bg-sunken">
                          <div className="absolute inset-y-0 left-1/2 w-px bg-[--line-strong]" />
                          <div
                            className={`absolute inset-y-0 ${positive ? "bg-red-500" : "bg-emerald-500"}`}
                            style={{
                              left: positive ? "50%" : `${50 - width}%`,
                              width: `${width}%`,
                            }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              {hazard.unobserved.length > 0 ? (
                <p className="mt-4 border-t pt-3 text-[11px] text-ink-faint">
                  Not observed, contributing nothing:{" "}
                  {hazard.unobserved.map((k) => k.replace(/_/g, " ")).join(", ")}
                </p>
              ) : null}
            </div>
          </section>

          <section className="card overflow-hidden">
            <div className="card-head">
              <span className="card-title">Method</span>
              <span className="text-[11px] text-ink-faint">{hazard.method}</span>
            </div>
            <ol className="space-y-2.5 px-5 py-4">
              {hazard.steps.map((step) => (
                <li key={step} className="text-[12px] leading-relaxed text-ink-soft">
                  {step}
                </li>
              ))}
            </ol>
            <div className="card-note">
              <ul className="space-y-1">
                {hazard.caveats.map((caveat) => (
                  <li key={caveat}>· {caveat}</li>
                ))}
              </ul>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
