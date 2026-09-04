"use client";

import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Ban,
  Bot,
  Cpu,
  Eye,
  Gavel,
  Lock,
  Megaphone,
  Pause,
  Play,
  Radar,
  RotateCcw,
  ScanSearch,
  Send,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";
import {
  fetchAgents,
  fetchChainRuns,
  fetchChainTrace,
  type AgentSpec,
  type AgentsPayload,
  type ChainRun,
  type ChainTrace,
} from "@/lib/agents";

const AGENT_ICON: Record<string, LucideIcon> = {
  scout: Radar,
  watcher: Eye,
  investigator: ScanSearch,
  verifier: Gavel,
  explainer: Megaphone,
  actor: Send,
  system: Cpu,
};

const AGENT_ACCENT: Record<string, string> = {
  scout: "border-sky-300 bg-sky-50 text-sky-700",
  watcher: "border-violet-300 bg-violet-50 text-violet-700",
  investigator: "border-amber-300 bg-amber-50 text-amber-700",
  verifier: "border-emerald-300 bg-emerald-50 text-emerald-700",
  explainer: "border-blue-300 bg-blue-50 text-blue-700",
  actor: "border-red-300 bg-red-50 text-red-700",
  system: "border-line bg-sunken text-ink-soft",
};

const KIND_TONE: Record<string, string> = {
  TRIGGER: "bg-sky-100 text-sky-800",
  WATCH: "bg-violet-100 text-violet-800",
  MEMORY: "bg-slate-100 text-ink-soft",
  STEP: "bg-amber-100 text-amber-800",
  TOOL: "bg-amber-50 text-amber-700",
  RETRY: "bg-orange-100 text-orange-800",
  VERIFY: "bg-emerald-100 text-emerald-800",
  EXPLAIN: "bg-blue-100 text-blue-800",
  ACTION: "bg-red-100 text-red-800",
  GATE: "bg-red-50 text-red-700",
  DEGRADED: "bg-orange-100 text-orange-800",
  ERROR: "bg-red-100 text-red-800",
  DONE: "bg-slate-100 text-ink-soft",
};

const ORDER = ["scout", "watcher", "investigator", "verifier", "explainer", "actor"];

function AgentCard({ agent, active }: { agent: AgentSpec; active: boolean }) {
  const Icon = AGENT_ICON[agent.key] ?? Bot;
  return (
    <div
      className={`card flex h-full flex-col overflow-hidden transition-shadow ${
        active ? "ring-2 ring-accent shadow-raised" : ""
      }`}
    >
      <div className="flex items-start gap-3 border-b px-4 py-3.5">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${
            AGENT_ACCENT[agent.key] ?? AGENT_ACCENT.system
          }`}
        >
          <Icon size={17} strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <div className="text-[14px] font-semibold leading-tight">{agent.name}</div>
          <div className="mt-0.5 text-[11.5px] leading-snug text-ink-muted">{agent.role}</div>
        </div>
      </div>

      <div className="flex-1 space-y-3 px-4 py-3">
        <div>
          <div className="label flex items-center gap-1.5">
            <Play size={10} /> fires when
          </div>
          <p className="mt-1 text-[11.5px] leading-snug text-ink-soft">{agent.fires_when}</p>
        </div>

        <div>
          <div className="label flex items-center gap-1.5">
            <ArrowDownToLine size={10} /> takes in
          </div>
          <ul className="mt-1 space-y-0.5">
            {agent.inputs.map((item) => (
              <li key={item} className="text-[11px] leading-snug text-ink-muted">
                {item}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="label flex items-center gap-1.5">
            <ArrowUpFromLine size={10} /> produces
          </div>
          <ul className="mt-1 space-y-0.5">
            {agent.outputs.map((item) => (
              <li key={item} className="text-[11px] leading-snug text-ink-soft">
                {item}
              </li>
            ))}
          </ul>
        </div>

        {agent.tools.length > 0 ? (
          <div>
            <div className="label">tools it may call</div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {agent.tools.map((tool) => (
                <span
                  key={tool.name}
                  title={tool.description}
                  className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
                    tool.gated
                      ? "border-red-200 bg-red-50 text-red-700"
                      : "border-line bg-sunken text-ink-muted"
                  }`}
                >
                  {tool.gated ? <Lock size={8} className="mr-0.5 inline" /> : null}
                  {tool.name}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="border-t bg-sunken px-4 py-2.5">
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
          <Bot size={11} /> autonomy
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">{agent.autonomy}</p>
        <div className="mt-2 font-mono text-[10px] text-ink-faint">
          {agent.routing.provider} / {agent.routing.model}
        </div>
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const [spec, setSpec] = useState<AgentsPayload | null>(null);
  const [runs, setRuns] = useState<ChainRun[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [trace, setTrace] = useState<ChainTrace | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    void fetchAgents().then(setSpec);
    void fetchChainRuns().then((data) => {
      setRuns(data?.runs ?? []);
      const first = data?.runs?.[0];
      if (first) setRunId(first.run_id);
    });
  }, []);

  useEffect(() => {
    if (!runId) return;
    setPlaying(false);
    setCursor(0);
    void fetchChainTrace(runId).then(setTrace);
  }, [runId]);

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (!playing || !trace) return;
    timer.current = setInterval(() => {
      setCursor((value) => {
        if (value >= trace.lines.length) {
          setPlaying(false);
          return value;
        }
        return value + 1;
      });
    }, 240);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing, trace]);

  const shown = useMemo(() => (trace ? trace.lines.slice(0, cursor) : []), [trace, cursor]);
  const activeAgent = shown.length > 0 ? (shown[shown.length - 1]?.agent ?? null) : null;
  const toolsSoFar = shown.filter((line) => line.kind === "TOOL").length;
  const orderedAgents = useMemo(
    () =>
      (spec?.agents ?? [])
        .slice()
        .sort((a, b) => ORDER.indexOf(a.key) - ORDER.indexOf(b.key)),
    [spec],
  );

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Agent theatre"
        title="Six agents, what each one is handed and what it hands on"
        lede="Every card below is read from the running system: the model each agent is routed to, the tools it is permitted to call, and where its authority stops. The replay underneath steps through a real recorded run, line by line."
      />

      <StatRow>
        <StatCard
          label="Agents in the chain"
          value={spec?.agents.length ?? 0}
          Icon={Workflow}
          tint="blue"
          foot="each with one job and one handoff"
        />
        <StatCard
          label="Deterministic tools"
          value={spec?.tool_count ?? 0}
          Icon={Cpu}
          tint="violet"
          foot="the model never computes a number"
        />
        <StatCard
          label="Investigator step limit"
          value={spec?.max_steps ?? 0}
          Icon={RotateCcw}
          tint="amber"
          foot="hard bound on the ReAct loop"
        />
        <StatCard
          label="Gated tools"
          value={spec?.gated_tools.length ?? 0}
          Icon={Ban}
          tint="red"
          foot="requested but never self executed"
        />
      </StatRow>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {orderedAgents.map((agent) => (
          <AgentCard
            key={agent.key}
            agent={agent}
            active={activeAgent === agent.key}
          />
        ))}
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[300px_1fr]">
        <aside className="card flex flex-col">
          <div className="border-b px-4 py-3">
            <span className="card-title">Recorded runs</span>
          </div>
          <div className="max-h-[430px] overflow-y-auto p-2">
            {runs.map((run) => (
              <button
                key={run.run_id}
                onClick={() => setRunId(run.run_id)}
                className={`mb-1 w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                  runId === run.run_id ? "bg-accent text-white" : "hover:bg-sunken"
                }`}
              >
                <div className="truncate font-mono text-[11.5px] font-medium">{run.run_id}</div>
                <div
                  className={`mt-1 flex gap-2.5 text-[10.5px] ${
                    runId === run.run_id ? "text-white/75" : "text-ink-faint"
                  }`}
                >
                  <span>{run.lines} lines</span>
                  <span>{run.tools} tools</span>
                  <span>{run.agents.length} agents</span>
                </div>
                {run.replay ? (
                  <span
                    className={`mt-1 inline-block rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.06em] ${
                      runId === run.run_id ? "bg-white/20" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    replay
                  </span>
                ) : null}
              </button>
            ))}
          </div>
          {trace ? (
            <div className="border-t px-4 py-3">
              <div className="label">Lines by agent</div>
              <ul className="mt-2 space-y-1.5">
                {Object.entries(trace.counts_by_agent).map(([key, count]) => {
                  const Icon = AGENT_ICON[key] ?? Bot;
                  return (
                    <li key={key} className="flex items-center gap-2">
                      <Icon size={12} className="text-ink-faint" />
                      <span className="flex-1 text-[11.5px] capitalize text-ink-soft">{key}</span>
                      <span className="font-mono text-[11.5px] text-ink-muted">{count}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </aside>

        <Section
          eyebrow="Live replay"
          title={runId ? `Stepping ${runId}` : "Select a run"}
          aside={
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-ink-faint">
                {cursor}/{trace?.lines.length ?? 0} lines, {toolsSoFar} tool calls
              </span>
              <button
                onClick={() => setCursor(0)}
                className="btn gap-1.5 px-2.5 py-1 text-[12px]"
              >
                <RotateCcw size={12} /> Reset
              </button>
              <button
                onClick={() => {
                  if (trace && cursor >= trace.lines.length) setCursor(0);
                  setPlaying(!playing);
                }}
                className="btn btn-primary gap-1.5 px-3 py-1 text-[12px]"
              >
                {playing ? <Pause size={12} /> : <Play size={12} />}
                {playing ? "Pause" : "Play"}
              </button>
            </div>
          }
          note="Nothing here is staged. These are the exact JSONL lines the agents wrote to disk during a real run, including retries, degradations and failures."
        >
          <div className="max-h-[430px] overflow-y-auto">
            {shown.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-16 text-center">
                <Workflow size={22} className="text-ink-faint" strokeWidth={1.6} />
                <p className="text-[13px] text-ink-muted">
                  Press <span className="font-semibold">Play</span> to watch the chain execute.
                </p>
              </div>
            ) : (
              <ol className="divide-y">
                {shown.map((line, index) => {
                  const Icon = AGENT_ICON[line.agent ?? "system"] ?? Bot;
                  return (
                    <li
                      key={`${line.ts}-${index}`}
                      className={`flex gap-3 px-5 py-2 ${
                        index === shown.length - 1 ? "bg-[--accent-soft]" : ""
                      } ${line.failed ? "bg-red-50" : ""}`}
                    >
                      <span className="w-6 shrink-0 pt-0.5 text-right font-mono text-[10px] text-ink-faint">
                        {index + 1}
                      </span>
                      <Icon size={13} className="mt-0.5 shrink-0 text-ink-faint" />
                      <span className="w-20 shrink-0 pt-0.5 text-[11px] capitalize text-ink-muted">
                        {line.agent ?? "system"}
                      </span>
                      <span
                        className={`h-fit shrink-0 rounded px-1.5 py-0.5 font-mono text-[9.5px] font-semibold ${
                          KIND_TONE[line.kind] ?? "bg-slate-100 text-ink-soft"
                        }`}
                      >
                        {line.kind}
                      </span>
                      <span className="min-w-0 flex-1 text-[11.5px] leading-snug text-ink-soft">
                        {line.message}
                        {line.replay ? (
                          <span className="ml-1.5 rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold uppercase text-amber-800">
                            replay
                          </span>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </Section>
      </div>
    </main>
  );
}
