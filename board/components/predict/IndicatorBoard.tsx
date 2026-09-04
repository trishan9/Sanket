"use client";

import type { IndicatorSpec, Observations } from "@/lib/predict";

const STATES: Array<{ value: "present" | "absent" | "unknown"; label: string; tone: string }> = [
  { value: "present", label: "Present", tone: "bg-red-600 text-white" },
  { value: "absent", label: "Absent", tone: "bg-emerald-600 text-white" },
  { value: "unknown", label: "Not observed", tone: "bg-[--ink-faint] text-white" },
];

function stateOf(value: boolean | null | undefined): "present" | "absent" | "unknown" {
  if (value === true) return "present";
  if (value === false) return "absent";
  return "unknown";
}

export function IndicatorBoard({
  indicators,
  observations,
  onChange,
}: {
  indicators: IndicatorSpec[];
  observations: Observations;
  onChange: (next: Observations) => void;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="card-head">
        <div>
          <div className="label">Evidence</div>
          <div className="mt-0.5 text-[17px] font-semibold tracking-[-0.01em]">
            Set what the sensors saw
          </div>
        </div>
        <span className="text-[11px] text-ink-faint">
          Not observed contributes a likelihood ratio of exactly 1.0
        </span>
      </div>
      <ul>
        {indicators.map((indicator) => {
          const current = stateOf(observations[indicator.key]);
          return (
            <li key={indicator.key} className="border-b px-5 py-3.5 last:border-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-[13.5px] font-medium">{indicator.label}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-faint">
                    <span className="font-mono text-ink-muted">
                      LR+ {indicator.likelihood_ratio_present}× · LR−{" "}
                      {indicator.likelihood_ratio_absent}×
                    </span>
                    <span>{indicator.citation}</span>
                  </div>
                </div>
                <div className="flex shrink-0 gap-1 rounded-md border p-1">
                  {STATES.map((option) => (
                    <button
                      key={option.value}
                      onClick={() =>
                        onChange({
                          ...observations,
                          [indicator.key]:
                            option.value === "unknown" ? null : option.value === "present",
                        })
                      }
                      className={`rounded px-2.5 py-1 text-[11.5px] font-medium transition-colors ${
                        current === option.value
                          ? option.tone
                          : "text-ink-muted hover:bg-sunken"
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
