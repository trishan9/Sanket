"use client";

import { useEffect, useState } from "react";
import { fetchCompleteness, type CompletenessPayload } from "@/lib/risk";

function cellColour(count: number, max: number, hue: string): string {
  if (count === 0) return "#1e232b";
  const intensity = Math.max(0.2, count / Math.max(1, max));
  return hue === "radar"
    ? `rgba(56, 160, 226, ${intensity})`
    : `rgba(216, 161, 26, ${intensity})`;
}

function Row({
  label,
  product,
  byMonth,
  months,
  max,
  hue,
}: {
  label: string;
  product: string;
  byMonth: Record<string, number>;
  months: string[];
  max: number;
  hue: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 shrink-0">
        <div className="text-xs font-medium">{label}</div>
        <div className="text-[10px] text-ink-faint">{product}</div>
      </div>
      <div className="flex flex-1 gap-0.5 overflow-x-auto">
        {months.map((month) => {
          const count = byMonth[month] ?? 0;
          return (
            <div
              key={month}
              title={`${month}: ${count} usable granules`}
              className="h-8 min-w-[18px] flex-1 rounded-sm"
              style={{ background: cellColour(count, max, hue) }}
            />
          );
        })}
      </div>
    </div>
  );
}

export function CompletenessHeatmap() {
  const [data, setData] = useState<CompletenessPayload | null>(null);

  useEffect(() => {
    void fetchCompleteness().then(setData);
  }, []);

  if (!data) {
    return (
      <section className="card card-pad">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Observation completeness
        </h2>
        <p className="mt-2 text-sm text-ink-muted">Loading granule coverage…</p>
      </section>
    );
  }

  const months = Array.from(
    new Set([...Object.keys(data.optical.by_month), ...Object.keys(data.radar.by_month)]),
  ).sort();
  const max = Math.max(
    1,
    ...Object.values(data.optical.by_month),
    ...Object.values(data.radar.by_month),
  );

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Observation completeness, tile {data.tile}
      </h2>
      <div className="mt-3 space-y-2">
        <Row
          label="Optical"
          product={data.optical.product}
          byMonth={data.optical.by_month}
          months={months}
          max={max}
          hue="optical"
        />
        <Row
          label="Radar"
          product={data.radar.product}
          byMonth={data.radar.by_month}
          months={months}
          max={max}
          hue="radar"
        />
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-ink-faint">
        <span>{months[0]}</span>
        <span>{months[months.length - 1]}</span>
      </div>
      <p className="mt-3 border-t border-line pt-3 text-[11px] text-ink-muted">{data.note}</p>
    </section>
  );
}
