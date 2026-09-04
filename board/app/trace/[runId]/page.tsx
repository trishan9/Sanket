"use client";

import { use, useEffect, useState } from "react";
import { fetchTrace } from "@/lib/api";
import type { TraceLine } from "@/lib/types";

const AGENT_COLOR: Record<string, string> = {
  scout: "text-fuchsia-400",
  watcher: "text-sky-400",
  investigator: "text-violet-400",
  verifier: "text-amber-400",
  explainer: "text-emerald-400",
  actor: "text-rose-400",
  system: "text-ink-muted",
};

function lineStyle(line: TraceLine): string {
  if (line.failed || line.kind === "ERROR" || line.kind === "REJECTED") return "text-red-400";
  if (line.kind === "DEGRADED") return "text-orange-400";
  if (line.kind === "DONE" || line.kind === "APPROVED") return "text-green-400";
  return AGENT_COLOR[line.agent] ?? "text-ink-soft";
}

function timestamp(ts: string): string {
  return ts.slice(11, 19);
}

export default function TraceDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const [lines, setLines] = useState<TraceLine[] | null>(null);

  useEffect(() => {
    void fetchTrace(runId).then((payload) => setLines(payload?.lines ?? []));
  }, [runId]);

  const isReplay = lines?.some((l) => l.replay) ?? false;

  return (
    <main className="w-full px-7 pb-16">
      <h1 className="text-lg font-semibold">Trace, {runId}</h1>
      {isReplay ? (
        <p className="mt-1 rounded border border-amber-700 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
          REPLAY, every line below is from a simulated run, not a live event
        </p>
      ) : null}
      {!lines ? (
        <p className="mt-4 text-ink-faint">Loading…</p>
      ) : lines.length === 0 ? (
        <p className="mt-4 text-ink-faint">No trace recorded for this run.</p>
      ) : (
        <pre className="mt-4 overflow-x-auto rounded-lg border bg-surface p-3 text-xs leading-relaxed">
          {lines.map((line, i) => {
            const indent = line.kind === "RETRY" ? "    " : "";
            return (
              <div key={i} className={lineStyle(line)}>
                {indent}[{timestamp(line.ts)}] {line.kind.padEnd(9)} {line.agent.padEnd(13)}{" "}
                {line.message}
                {line.tokens_in !== null || line.tokens_out !== null
                  ? ` · ${(line.tokens_in ?? 0) + (line.tokens_out ?? 0)} tok`
                  : ""}
                {line.cost_npr !== null ? ` · NPR ${line.cost_npr.toFixed(4)}` : ""}
              </div>
            );
          })}
        </pre>
      )}
    </main>
  );
}
