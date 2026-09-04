"use client";

import { useEffect, useState } from "react";
import type { TraceLine } from "@/lib/types";

const AGENTS = [
  { key: "scout", label: "Scout", job: "decides which corridors deserve a close watch" },
  { key: "watcher", label: "Watcher", job: "decides whether anything is worth investigating" },
  { key: "investigator", label: "Investigator", job: "works out what happened and what it means" },
  { key: "verifier", label: "Verifier", job: "decides whether the conclusions are supported" },
  { key: "explainer", label: "Explainer", job: "makes the decision legible" },
  { key: "actor", label: "Actor", job: "makes something change in the world" },
] as const;

const KIND_TO_AGENT: Record<string, string> = {
  TRIGGER: "watcher",
  WATCH: "watcher",
  MEMORY: "scout",
  STEP: "investigator",
  TOOL: "investigator",
  RETRY: "investigator",
  VERIFY: "verifier",
  EXPLAIN: "explainer",
  ACTION: "actor",
  GATE: "actor",
  DEGRADED: "investigator",
  DONE: "actor",
};

export function AgentPanel({ lines }: { lines: TraceLine[] }) {
  const [active, setActive] = useState<Set<string>>(new Set());

  useEffect(() => {
    const seen = new Set<string>();
    for (const line of lines) {
      const agent = line.agent ?? KIND_TO_AGENT[line.kind];
      if (agent) seen.add(agent.toLowerCase());
    }
    setActive(seen);
  }, [lines]);

  const counts = new Map<string, number>();
  for (const line of lines) {
    const agent = (line.agent ?? KIND_TO_AGENT[line.kind] ?? "").toLowerCase();
    if (agent) counts.set(agent, (counts.get(agent) ?? 0) + 1);
  }

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Six agents
      </h2>
      <ol className="mt-3 space-y-1.5">
        {AGENTS.map((agent, index) => {
          const lit = active.has(agent.key);
          const count = counts.get(agent.key) ?? 0;
          return (
            <li
              key={agent.key}
              className={`flex items-center gap-3 rounded border px-3 py-2 transition-colors ${
                lit
                  ? "border-accent/40 bg-[--accent-soft]"
                  : "border-line bg-sunken opacity-60"
              }`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                  lit ? "bg-accent text-white" : "bg-[--surface-sunken] text-ink-faint"
                }`}
              >
                {index + 1}
              </span>
              <span className="w-24 shrink-0 text-sm font-medium">{agent.label}</span>
              <span className="flex-1 truncate text-[11px] text-ink-faint">{agent.job}</span>
              {count > 0 ? (
                <span className="shrink-0 rounded bg-[--surface-sunken] px-2 py-0.5 font-mono text-[10px] text-ink-soft">
                  {count}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-[11px] text-ink-faint">
        Lit agents appear in this run&apos;s trace. Tier 0 and Tier 1 detection make zero model
        calls by design.
      </p>
    </section>
  );
}
