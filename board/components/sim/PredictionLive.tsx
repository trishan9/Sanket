"use client";

import { Image as ImageIcon, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { fetchHazard, type HazardPayload } from "@/lib/predict";

const API_BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

type State = "present" | "absent" | "unobserved";

interface Row {
  key: string;
  label: string;
  present: number;
  absent: number;
  note: string;
}

const INDICATORS: Row[] = [
  {
    key: "seismic_landslide_type",
    label: "Landslide-type seismic event",
    present: 42.0,
    absent: 0.85,
    note: "The dominant impoundment mechanism here, and near instantaneous",
  },
  {
    key: "radar_water_anomaly",
    label: "Radar water anomaly",
    present: 6.0,
    absent: 0.55,
    note: "Radar sees through cloud, so absence is real evidence",
  },
  {
    key: "upstream_mass_movement",
    label: "Confirmed disturbance upstream",
    present: 8.5,
    absent: 0.8,
    note: "Cloud limits detection, so absence is weak evidence",
  },
  {
    key: "lake_area_growth",
    label: "Sustained lake-area growth",
    present: 3.2,
    absent: 0.7,
    note: "A conditioning trend, not a trigger",
  },
  {
    key: "antecedent_precip_extreme",
    label: "Extreme antecedent rainfall",
    present: 2.1,
    absent: 0.95,
    note: "Both corridor events happened on unremarkable rainfall days",
  },
  {
    key: "temperature_anomaly",
    label: "Positive temperature anomaly",
    present: 1.6,
    absent: 1.0,
    note: "Absence is treated as telling you nothing at all",
  },
];

const START: Record<string, State> = Object.fromEntries(
  INDICATORS.map((row) => [row.key, "unobserved" as State]),
);

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function StateButton({
  active,
  tone,
  label,
  onClick,
}: {
  active: boolean;
  tone: "on" | "off" | "none";
  label: string;
  onClick: () => void;
}) {
  const tint =
    tone === "on"
      ? "bg-level-red text-white border-level-red"
      : tone === "off"
        ? "bg-level-green text-white border-level-green"
        : "bg-sunken text-ink-muted";
  return (
    <button
      onClick={onClick}
      className={`rounded border px-2 py-1 text-[10.5px] font-medium transition-colors ${
        active ? tint : "text-ink-faint hover:bg-sunken"
      }`}
    >
      {label}
    </button>
  );
}

export function PredictionLive({ nodeId = "lhende_barrier" }: { nodeId?: string }) {
  const [states, setStates] = useState<Record<string, State>>(START);
  const [hazard, setHazard] = useState<HazardPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    const observations: Record<string, boolean | null> = {};
    for (const row of INDICATORS) {
      const state = states[row.key];
      observations[row.key] = state === "unobserved" ? null : state === "present";
    }
    setHazard(await fetchHazard(nodeId, observations, 7, 1));
    setBusy(false);
  }, [states, nodeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const showCard = async () => {
    setRendering(true);
    const level = (hazard?.posterior_probability ?? 0) >= 0.6 ? "RED" : "ORANGE";
    try {
      const response = await fetch(
        `${API_BASE}/api/floodcard?settlement=Timure&level=${level}`,
        { cache: "no-store" },
      );
      const payload = (await response.json()) as { image_url?: string };
      setCard(payload.image_url ? `${API_BASE}${payload.image_url}` : null);
    } catch {
      setCard(null);
    }
    setRendering(false);
  };

  const posterior = hazard?.posterior_probability ?? 0;
  const prior = hazard?.prior_probability ?? 0;
  const interval = hazard?.credible_interval ?? [0, 0];

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <div className="label">Live prediction</div>
          <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
            Turn evidence on and watch the probability move
          </div>
        </div>
        <button onClick={() => setStates(START)} className="btn">
          <RotateCcw size={13} /> Reset to prior
        </button>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1fr_320px]">
        <div className="border-b p-4 lg:border-b-0 lg:border-r">
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr>
                <th className="pb-2 text-[9.5px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
                  Indicator
                </th>
                <th className="pb-2 text-right text-[9.5px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
                  LR
                </th>
                <th className="pb-2 text-right text-[9.5px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
                  Observed
                </th>
              </tr>
            </thead>
            <tbody>
              {INDICATORS.map((row) => {
                const state = states[row.key] ?? "unobserved";
                const ratio =
                  state === "present" ? row.present : state === "absent" ? row.absent : 1.0;
                return (
                  <tr key={row.key} className="border-t align-top">
                    <td className="py-2 pr-2">
                      <div className="font-medium">{row.label}</div>
                      <div className="text-[10.5px] leading-tight text-ink-faint">{row.note}</div>
                    </td>
                    <td className="py-2 pr-2 text-right font-mono text-[12px]">
                      ×{ratio.toFixed(2)}
                    </td>
                    <td className="py-2">
                      <div className="flex justify-end gap-1">
                        {(["present", "absent", "unobserved"] as const).map((option) => (
                          <StateButton
                            key={option}
                            active={state === option}
                            tone={
                              option === "present" ? "on" : option === "absent" ? "off" : "none"
                            }
                            label={
                              option === "present" ? "yes" : option === "absent" ? "no" : "n/a"
                            }
                            onClick={() =>
                              setStates((current) => ({ ...current, [row.key]: option }))
                            }
                          />
                        ))}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="p-4">
          <div className="label">Probability of an outburst in 7 days</div>
          <div
            className="mt-1 font-mono text-[40px] font-semibold leading-none tracking-[-0.03em]"
            style={{
              color:
                posterior >= 0.6
                  ? "var(--red)"
                  : posterior >= 0.25
                    ? "var(--orange)"
                    : "var(--green)",
            }}
          >
            {busy ? "…" : pct(posterior)}
          </div>
          <div className="mt-1.5 text-[11.5px] text-ink-muted">
            90% credible interval {pct(interval[0])} to {pct(interval[1])}
          </div>

          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-sunken">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.max(posterior * 100, 1)}%`,
                background:
                  posterior >= 0.6
                    ? "var(--red)"
                    : posterior >= 0.25
                      ? "var(--orange)"
                      : "var(--green)",
              }}
            />
          </div>

          <dl className="mt-3 space-y-1 text-[12px]">
            <div className="flex justify-between border-b py-1">
              <dt className="text-ink-muted">Base rate before evidence</dt>
              <dd className="font-mono">{pct(prior)}</dd>
            </div>
            <div className="flex justify-between border-b py-1">
              <dt className="text-ink-muted">Evidence lift</dt>
              <dd className="font-mono">×{(hazard?.lift ?? 1).toFixed(2)}</dd>
            </div>
            <div className="flex justify-between border-b py-1">
              <dt className="text-ink-muted">Strongest evidence</dt>
              <dd className="font-mono text-[11px]">{hazard?.dominant_indicator ?? "none yet"}</dd>
            </div>
            <div className="flex justify-between py-1">
              <dt className="text-ink-muted">Not observed</dt>
              <dd className="font-mono">{hazard?.unobserved.length ?? 0} of 6</dd>
            </div>
          </dl>

          <button
            onClick={() => void showCard()}
            disabled={rendering}
            className="btn btn-primary mt-4 w-full justify-center disabled:opacity-50"
          >
            <ImageIcon size={14} />
            {rendering ? "Routing the flood" : "Show the flood map for this"}
          </button>

          {card ? (
            <img
              src={card}
              alt="Modelled flood path for this scenario"
              className="mt-3 w-full rounded-md border"
            />
          ) : null}
        </div>
      </div>

      <div className="card-note">
        Prior is the Costa and Schuster 1988 survival model for a dam that has already formed,
        conditioned on how long it has held. Each indicator multiplies the odds by its likelihood
        ratio. The interval comes from 20,000 Monte Carlo draws over the failure ceiling and the
        median timing, so it widens when the record is thin rather than narrowing.
      </div>
    </section>
  );
}
