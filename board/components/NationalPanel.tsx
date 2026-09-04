"use client";

import { useEffect, useState } from "react";
import { ageLabel, fetchNational } from "@/lib/api";
import type { NationalSummary } from "@/lib/api";

export function NationalPanel() {
  const [summary, setSummary] = useState<NationalSummary | null>(null);

  useEffect(() => {
    void fetchNational().then(setSummary);
  }, []);

  if (!summary || summary.basins_swept === 0) {
    return (
      <section className="mt-4 card card-pad">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          National picture
        </h2>
        <p className="mt-2 text-sm text-ink-faint">No sweep recorded yet.</p>
      </section>
    );
  }

  const { active = 0, standing = 0, survey = 0 } = summary.tier_counts;

  return (
    <section className="mt-4 card card-pad">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          National picture
        </h2>
        <span className="text-xs text-ink-faint">
          {summary.basins_swept} basins swept · {ageLabel(summary.last_swept_at)}
        </span>
      </div>
      <div className="mt-2 flex gap-4 text-sm">
        <span className="text-yellow-400">{active} active</span>
        <span className="text-sky-400">{standing} standing</span>
        <span className="text-ink-muted">{survey} survey</span>
      </div>
    </section>
  );
}
