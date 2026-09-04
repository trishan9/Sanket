"use client";

import { useEffect, useState } from "react";
import { fetchCascade, type CascadePayload } from "@/lib/risk";

const NODE_COLOR: Record<string, string> = {
  barrier_lake: "#c0212f",
  landslide_dam: "#c0212f",
  debris_dam: "#e0692a",
  supraglacial_lake: "#7c2ca8",
  moraine_lake: "#7c2ca8",
  ice_dammed_lake: "#2781d6",
  reservoir: "#1f8a4c",
  confluence: "#d8a11a",
  settlement: "#5c6470",
};

function confidenceWidth(confidence: number): string {
  return `${Math.max(6, Math.round(confidence * 100))}%`;
}

export function CascadeGraph({ nodeId = "lhende_barrier" }: { nodeId?: string }) {
  const [data, setData] = useState<CascadePayload | null>(null);

  useEffect(() => {
    void fetchCascade(nodeId).then(setData);
  }, [nodeId]);

  if (!data) {
    return (
      <section className="card card-pad">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Cascade chain
        </h2>
        <p className="mt-2 text-sm text-ink-muted">Loading cascade from {nodeId}…</p>
      </section>
    );
  }

  return (
    <section className="card card-pad">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Cascade chain from {data.origin}
        </h2>
        <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
          SCENARIO
        </span>
      </div>

      <p className="mt-1 text-xs text-ink-muted">
        Confidence decays ×{data.decay_per_step.toFixed(2)} per step, a longer chain cannot carry
        the confidence of a short one.
      </p>

      <ol className="mt-4 space-y-3">
        {data.steps.map((step) => (
          <li key={step.node_id} className="relative">
            <div className="flex items-center gap-3">
              <span
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ background: NODE_COLOR[step.node_type] ?? "#5c6470" }}
              />
              <span className="w-40 shrink-0 truncate text-sm font-medium">{step.node_id}</span>
              <span className="w-32 shrink-0 text-[11px] uppercase tracking-wide text-ink-faint">
                {step.node_type.replace(/_/g, " ")}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded bg-[--surface-sunken]">
                <div
                  className="h-full rounded bg-accent"
                  style={{ width: confidenceWidth(step.confidence) }}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-xs text-ink-soft">
                {step.confidence.toFixed(2)}
              </span>
            </div>
            <p className="ml-6 mt-1 text-xs text-ink-faint">{step.mechanism}</p>
            {step.note ? (
              <p className="ml-6 text-[11px] text-amber-700">{step.note}</p>
            ) : null}
          </li>
        ))}
      </ol>

      <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[11px] text-ink-faint">
        {data.caveats.map((caveat) => (
          <li key={caveat}>· {caveat}</li>
        ))}
      </ul>
    </section>
  );
}
