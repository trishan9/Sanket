"use client";

import { Inbox, PlayCircle, ShieldCheck, Timer } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { GateCard } from "@/components/gate/GateCard";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";
import { fetchDrill, fetchGateQueue, startDrill, type DrillState, type GateQueue } from "@/lib/control";

const STAGES = [
  { key: "scout", label: "Scout sweeps 8 basins", detail: "tier scoring, no model call" },
  { key: "watcher", label: "Watcher checks the corridor", detail: "radar delta against 14 observations" },
  { key: "investigator", label: "Investigator opens a case", detail: "tool calls until it concludes or hits step 10" },
  { key: "verifier", label: "Verifier re-derives every claim", detail: "a claim that fails is vetoed, not softened" },
  { key: "explainer", label: "Explainer scores the decision", detail: "contributions and flip points" },
  { key: "actor", label: "Actor stops at the gate", detail: "anything above YELLOW needs a person" },
];

export default function GatePage() {
  const [queue, setQueue] = useState<GateQueue | null>(null);
  const [drill, setDrill] = useState<DrillState | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    void fetchGateQueue().then(setQueue);
  }, []);

  useEffect(() => {
    refresh();
    const handle = setInterval(refresh, 5000);
    return () => clearInterval(handle);
  }, [refresh]);

  useEffect(() => {
    if (!drill || drill.state !== "running") return;
    timer.current = setInterval(() => {
      void fetchDrill(drill.drill_id).then((next) => {
        if (next) setDrill(next);
        refresh();
      });
    }, 4000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [drill, refresh]);

  const pending = queue?.pending ?? [];
  const running = drill?.state === "running";

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Human in the loop"
        title="Nothing above YELLOW leaves this building without a signature"
        lede="The agents run the whole chain on their own and then stop here. This is the only screen where a public alert is released, and the release is signed by a named contact."
      />

      <StatRow>
        <StatCard label="Waiting on a person" value={pending.length} Icon={Inbox} tint="amber" foot="pending gate requests" />
        <StatCard label="Autonomy ceiling" value="YELLOW" Icon={ShieldCheck} tint="green" foot="GREEN, GREY, YELLOW post themselves" />
        <StatCard label="Gate window" value="30 min" Icon={Timer} tint="blue" foot="then it expires unsent" />
        <StatCard label="Registered approver" value={queue?.approver ? "set" : "none"} Icon={ShieldCheck} tint="violet" foot={queue?.approver ?? "APPROVER_CONTACT unset"} />
      </StatRow>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_1fr]">
        <Section
          eyebrow="Trigger"
          title="Run the whole chain against the 26 August 2026 event"
          note="Replays the real Lhende barrier case through Scout, Watcher, Investigator, Verifier, Explainer and Actor. Every alert it produces is stamped REPLAY - TEST."
        >
          <div className="p-5">
            <button
              onClick={() => void startDrill().then(setDrill)}
              disabled={running}
              className="btn btn-primary disabled:opacity-50"
            >
              <PlayCircle size={15} /> {running ? "Chain running" : "Start replay drill"}
            </button>

            {drill ? (
              <div className="mt-4 rounded-md border bg-sunken p-3 text-[12px]">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="font-mono text-[11px]">{drill.drill_id}</span>
                  <span className="font-medium">{drill.state}</span>
                  {drill.elapsed_seconds ? <span>{drill.elapsed_seconds} s wall clock</span> : null}
                  {drill.investigated != null ? <span>{drill.investigated} investigated</span> : null}
                </div>
                {drill.error ? <p className="mt-1.5 text-level-red">{drill.error}</p> : null}
                {drill.latest_run_id ? (
                  <p className="mt-1.5 font-mono text-[11px] text-ink-muted">{drill.latest_run_id}</p>
                ) : null}
                {running ? (
                  <p className="mt-1.5 text-ink-muted">
                    Takes about four minutes. The investigator is making real tool calls, not
                    replaying a recording.
                  </p>
                ) : null}
              </div>
            ) : null}

            <ol className="mt-4 space-y-0">
              {STAGES.map((stage, index) => (
                <li key={stage.key} className="flex gap-3 border-b py-2.5 last:border-0">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold text-ink-muted">
                    {index + 1}
                  </span>
                  <span>
                    <span className="block text-[13px] font-medium leading-tight">{stage.label}</span>
                    <span className="block text-[11px] leading-tight text-ink-faint">{stage.detail}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </Section>

        <Section
          eyebrow="Delivery"
          title="What approval actually does"
          note="One press fans the message out over Twilio WhatsApp and records a delivery receipt per recipient."
        >
          <div className="space-y-2.5 p-5 text-[12.5px] leading-relaxed text-ink-soft">
            <p>
              Approval writes the decision, the timestamp and the approver contact into the gates
              table, then releases in two tiers: institutional contacts get the score and the
              evidence summary, residents get the portrait card in Nepali and English with the
              modelled flood path and their own arrival estimate.
            </p>
            <p>
              A per settlement cooldown suppresses a repeat inside the window, so an approval storm
              cannot turn into a message storm. Every send returns a Twilio SID that is stored
              against the run, and the delivery status webhook updates it in place.
            </p>
            <p>
              Rejecting closes the gate and sends nothing. Letting the 30 minute window lapse does
              the same thing. Silence is never treated as consent.
            </p>
          </div>
        </Section>
      </div>

      <div className="mt-4 space-y-4">
        {pending.length === 0 ? (
          <div className="card card-pad text-center text-[12.5px] text-ink-muted">
            No gate is waiting. Start a replay drill above to put one here.
          </div>
        ) : (
          pending.map((gate) => (
            <GateCard key={gate.gate_id} gate={gate} approver={queue?.approver ?? null} onDecided={refresh} />
          ))
        )}
      </div>
    </main>
  );
}
