"use client";

import { useEffect, useState } from "react";
import { fetchValidation, type ValidationPayload } from "@/lib/risk";

function bar(value: number, colour: string) {
  return (
    <span className="block h-1.5 w-20 overflow-hidden rounded bg-[--surface-sunken]">
      <span
        className="block h-full"
        style={{ width: `${Math.round(value * 100)}%`, background: colour }}
      />
    </span>
  );
}

export function ValidationPanel() {
  const [data, setData] = useState<ValidationPayload | null>(null);

  useEffect(() => {
    void fetchValidation().then(setData);
  }, []);

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Validation against observed flood extents
      </h2>
      {!data ? (
        <p className="mt-2 text-sm text-ink-muted">Computing confusion matrix…</p>
      ) : (
        <>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead className="text-[11px] uppercase tracking-wide text-ink-faint">
                <tr>
                  <th className="py-1 pr-3">Scenario</th>
                  <th className="py-1 pr-3">Reference</th>
                  <th className="py-1 pr-3">Precision</th>
                  <th className="py-1 pr-3">Recall</th>
                  <th className="py-1 pr-3">IoU</th>
                  <th className="py-1 pr-3">TP / FP / FN</th>
                </tr>
              </thead>
              <tbody className="text-ink-soft">
                {data.rows.map((row) => (
                  <tr key={`${row.scenario}-${row.reference}`} className="border-t border-line">
                    <td className="py-2 pr-3">{row.scenario}</td>
                    <td className="py-2 pr-3 text-ink-muted">{row.reference}</td>
                    <td className="py-2 pr-3">
                      <span className="font-mono">{row.precision.toFixed(3)}</span>
                      {bar(row.precision, "#1f8a4c")}
                    </td>
                    <td className="py-2 pr-3">
                      <span className="font-mono">{row.recall.toFixed(3)}</span>
                      {bar(row.recall, "#c0212f")}
                    </td>
                    <td className="py-2 pr-3 font-mono">{row.iou.toFixed(3)}</td>
                    <td className="py-2 pr-3 font-mono text-ink-faint">
                      {row.true_positive} / {row.false_positive} / {row.false_negative}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-muted">
            {data.reading}
          </p>
          <p className="mt-2 text-[11px] text-ink-faint">
            Source: Copernicus EMS EMSR927 and HDX hot_flood_npl, computed live against the
            precomputed scenario grid.
          </p>
        </>
      )}
    </section>
  );
}
