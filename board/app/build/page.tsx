"use client";

import { useEffect, useState } from "react";
import { fetchProgress } from "@/lib/api";

interface Phase {
  id: number;
  name: string;
  state: string;
  estimated_hours: number;
  blocked_on: string[];
  checkpoint?: boolean;
}

interface Progress {
  state?: string;
  phases_complete?: number;
  phases_total?: number;
  estimated_hours_total?: number;
  phases?: Phase[];
}

const STATE_STYLE: Record<string, string> = {
  complete: "text-green-400",
  in_progress: "text-yellow-400",
  not_started: "text-ink-faint",
};

export default function BuildPage() {
  const [progress, setProgress] = useState<Progress | null>(null);

  useEffect(() => {
    void fetchProgress().then((value) => setProgress(value as Progress | null));
  }, []);

  if (!progress) {
    return <main className="p-8 text-ink-muted">Loading build progress…</main>;
  }

  return (
    <main className="w-full px-7 pb-16">
      <h1 className="text-lg font-semibold">SANKET, build progress</h1>
      <p className="mt-1 text-sm text-ink-muted">
        {progress.phases_complete ?? 0} / {progress.phases_total ?? 15} phases ·{" "}
        {progress.estimated_hours_total ?? 0} estimated hours
      </p>
      <p className="mt-1 text-xs text-ink-faint">{progress.state}</p>
      <ol className="mt-4 space-y-1">
        {(progress.phases ?? []).map((phase) => (
          <li
            key={phase.id}
            className="flex items-center justify-between rounded border bg-surface px-3 py-2 text-sm"
          >
            <span>
              <span className="text-ink-faint">{phase.id}</span> {phase.name}
              {phase.checkpoint ? <span className="ml-2 text-xs text-sky-400">checkpoint</span> : null}
            </span>
            <span className={STATE_STYLE[phase.state] ?? "text-ink-faint"}>{phase.state}</span>
          </li>
        ))}
      </ol>
    </main>
  );
}
