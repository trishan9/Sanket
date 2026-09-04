"use client";

import {
  BellRing,
  CheckCircle2,
  Clock,
  Play,
  Send,
  ShieldAlert,
  Siren,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";
import {
  fetchLadder,
  simulateEscalation,
  type EscalationPayload,
  type LadderStage,
} from "@/lib/predict";
import { fetchAlertHistory, type AlertHistory } from "@/lib/ops";

const LEVEL_STYLE: Record<string, string> = {
  GREEN: "border-emerald-300 bg-emerald-50 text-emerald-800",
  GREY: "border-line bg-sunken text-ink-soft",
  YELLOW: "border-amber-300 bg-amber-50 text-amber-800",
  ORANGE: "border-orange-300 bg-orange-50 text-orange-800",
  RED: "border-red-300 bg-red-50 text-red-800",
};

const LEVEL_BAR: Record<string, string> = {
  GREEN: "bg-level-green",
  GREY: "bg-level-grey",
  YELLOW: "bg-level-yellow",
  ORANGE: "bg-level-orange",
  RED: "bg-level-red",
};

const SCRIPT = [
  {
    at: "T+0 min",
    label: "Radar sees a step change, nothing corroborates it",
    indicators: 1,
    probability: 0.08,
    passed: false,
    vetoed: false,
  },
  {
    at: "T+90 min",
    label: "Seismic landslide-type event and disturbance agree",
    indicators: 3,
    probability: 0.55,
    passed: false,
    vetoed: false,
  },
  {
    at: "T+3 h",
    label: "Verifier accepts the claim, Explainer produces a decision",
    indicators: 3,
    probability: 0.92,
    passed: true,
    vetoed: false,
  },
  {
    at: "T+30 h",
    label: "Water drops, the evidence that raised this is gone",
    indicators: 0,
    probability: 0.01,
    passed: false,
    vetoed: false,
  },
];

function maskContact(value: string | null): string {
  if (!value) return "";
  const digits = value.replace(/\D/g, "");
  if (digits.length < 4) return "approver on file";
  return `approver ending ${digits.slice(-3)}`;
}

function shortTime(iso: string | null): string {
  if (!iso) return "not sent";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 16);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AlertsPage() {
  const [stages, setStages] = useState<LadderStage[]>([]);
  const [history, setHistory] = useState<AlertHistory | null>(null);
  const [timeline, setTimeline] = useState<EscalationPayload[]>([]);
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    void fetchLadder().then((data) => setStages(data?.stages ?? []));
    const load = () => void fetchAlertHistory().then(setHistory);
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  const run = async () => {
    setRunning(true);
    setTimeline([]);
    setStep(0);
    let previous: string | null = null;
    const collected: EscalationPayload[] = [];
    for (let index = 0; index < SCRIPT.length; index += 1) {
      const beat = SCRIPT[index]!;
      const result = await simulateEscalation(
        beat.indicators,
        beat.probability,
        beat.passed,
        beat.vetoed,
        previous,
      );
      if (result) {
        collected.push(result);
        previous = result.stage;
        setTimeline([...collected]);
        setStep(index + 1);
      }
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    setRunning(false);
  };

  const gatesHeld = history?.gates.filter((g) => !g.decision).length ?? 0;
  const autoSent = history?.notifications.length ?? 0;
  const runsWithDegradation =
    history?.runs.filter((r) => (r.degradations ?? []).length > 0).length ?? 0;
  const spend = useMemo(
    () => (history?.runs ?? []).reduce((total, run) => total + (run.cost_npr ?? 0), 0),
    [history],
  );

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Multi-step alerting"
        title="Warn early, correct later, stand down out loud"
        lede="An unverified change goes out within seconds as a GREY advisory, without waiting for a human. Only corroborated and verified stages ask anyone to move, and both hold at the district gate."
        aside={
          <button onClick={() => void run()} disabled={running} className="btn btn-primary gap-2">
            <Play size={15} strokeWidth={2.4} />
            {running ? `Running ${step}/${SCRIPT.length}` : "Play a real escalation"}
          </button>
        }
      />

      <StatRow>
        <StatCard
          label="Messages recorded"
          value={autoSent}
          Icon={Send}
          tint="blue"
          foot="rows in the notifications ledger"
        />
        <StatCard
          label="Gates awaiting a decision"
          value={gatesHeld}
          Icon={ShieldAlert}
          tint="amber"
          foot="nothing releases until answered"
        />
        <StatCard
          label="Runs that degraded"
          value={runsWithDegradation}
          Icon={Zap}
          tint="violet"
          foot="provider failover recorded in trace"
        />
        <StatCard
          label="Model spend"
          value={`NPR ${spend.toFixed(2)}`}
          Icon={Clock}
          tint="slate"
          foot={`across ${history?.runs.length ?? 0} recorded runs`}
        />
      </StatRow>

      <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {stages.map((stage) => (
          <div key={stage.stage} className={`card overflow-hidden ${LEVEL_STYLE[stage.level] ?? ""}`}>
            <div className={`h-1 w-full ${LEVEL_BAR[stage.level] ?? "bg-level-grey"}`} />
            <div className="px-4 py-3.5">
              <div className="flex items-center gap-2">
                {stage.autonomous ? (
                  <Zap size={14} strokeWidth={2.4} />
                ) : (
                  <ShieldAlert size={14} strokeWidth={2.4} />
                )}
                <span className="text-[12px] font-bold uppercase tracking-[0.07em]">
                  {stage.level}
                </span>
              </div>
              <div className="mt-2 text-[13px] font-semibold leading-snug">{stage.headline}</div>
              <div className="nepali mt-1 text-[12.5px] leading-snug opacity-80">
                {stage.headline_nepali}
              </div>
              <div className="mt-3 inline-flex rounded border border-current/25 px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.06em]">
                {stage.autonomous ? "sent autonomously" : "held at the gate"}
              </div>
            </div>
          </div>
        ))}
      </section>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_1fr]">
        <Section
          eyebrow="Worked example"
          title="One event, four messages"
          aside={<span className="text-[11px] text-ink-faint">real escalation engine</span>}
          note="The advisory stage sits below the autonomous ceiling so it can go out without a human. Nothing that tells a person to move is sent without recorded approval."
        >
          {timeline.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-5 py-12 text-center">
              <Siren size={22} className="text-ink-faint" strokeWidth={1.6} />
              <p className="text-[13px] text-ink-muted">
                Press <span className="font-semibold">Play a real escalation</span> to step an
                anomaly through the ladder.
              </p>
            </div>
          ) : (
            <ol>
              {timeline.map((entry, index) => {
                const beat = SCRIPT[index]!;
                return (
                  <li key={entry.at} className="flex gap-4 border-b px-5 py-3.5 last:border-0">
                    <div className="w-16 shrink-0 pt-0.5 font-mono text-[11.5px] font-semibold">
                      {beat.at}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`chip ${LEVEL_STYLE[entry.level] ?? ""}`}>
                          {entry.level}
                        </span>
                        <span className="text-[13px] font-semibold">{entry.headline}</span>
                        <span
                          className={`ml-auto inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.05em] ${
                            entry.autonomous
                              ? "bg-emerald-50 text-emerald-800"
                              : "bg-amber-50 text-amber-800"
                          }`}
                        >
                          {entry.autonomous ? <Zap size={11} /> : <ShieldAlert size={11} />}
                          {entry.autonomous ? "auto" : "gate"}
                        </span>
                      </div>
                      <p className="mt-1 text-[12px] text-ink-muted">{beat.label}</p>
                      <p className="mt-0.5 text-[12px] text-ink-soft">{entry.reason}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </Section>

        <Section
          eyebrow="Live ledger"
          title="What this system actually sent"
          aside={
            <span className="text-[11px] text-ink-faint">
              {history?.last_heartbeat ? `heartbeat ${shortTime(history.last_heartbeat.at)}` : ""}
            </span>
          }
          note="Every row is a real record from the operational database, including simulated-channel sends which are declared as such on the Solution Sheet."
        >
          <div className="max-h-[420px] overflow-y-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="sticky top-0 bg-sunken">
                <tr>
                  <th className="px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Settlement
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Channel
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Status
                  </th>
                  <th className="px-5 py-2 text-right text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                    Sent
                  </th>
                </tr>
              </thead>
              <tbody>
                {(history?.notifications ?? []).map((row) => (
                  <tr key={row.notification_id} className="border-b last:border-0">
                    <td className="px-5 py-2 font-medium">{row.settlement}</td>
                    <td className="px-3 py-2 text-ink-muted">{row.channel}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[11px]">
                        {row.delivery_status}
                      </span>
                    </td>
                    <td className="px-5 py-2 text-right font-mono text-[11px] text-ink-muted">
                      {shortTime(row.sent_at)}
                    </td>
                  </tr>
                ))}
                {(history?.notifications ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-ink-muted">
                      No messages recorded yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Section>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.15fr]">
        <Section eyebrow="Current board" title="Level held per settlement">
          <ul className="px-5 py-3">
            {(history?.statuses ?? []).map((row) => (
              <li key={row.settlement} className="flex items-center gap-3 border-b py-2.5 last:border-0">
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                    LEVEL_BAR[row.level] ?? "bg-level-grey"
                  }`}
                />
                <span className="w-36 shrink-0 truncate text-[13px] font-medium">
                  {row.settlement}
                </span>
                <span className="chip border-line bg-sunken text-ink-soft">{row.level}</span>
                <span className="ml-auto font-mono text-[12px] text-ink-muted">
                  {row.lead_time_minutes !== null
                    ? `${Math.round(row.lead_time_minutes)} min`
                    : "no arrival"}
                </span>
                <span className="w-16 shrink-0 text-right text-[11px] text-ink-faint">
                  {row.confidence ?? "unrated"}
                </span>
              </li>
            ))}
          </ul>
        </Section>

        <Section
          eyebrow="Approval gate"
          title="Requests and decisions"
          note="A gate that expires unanswered escalates to the next named contact and is logged, rather than waiting silently on one phone."
        >
          {(history?.gates ?? []).length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
              <CheckCircle2 size={20} className="text-ink-faint" strokeWidth={1.6} />
              <p className="text-[13px] text-ink-muted">No gate requests recorded.</p>
            </div>
          ) : (
            <ul>
              {(history?.gates ?? []).map((gate) => (
                <li key={gate.gate_id} className="border-b px-5 py-3 last:border-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <BellRing size={13} className="text-ink-faint" />
                    <span className="font-mono text-[12px] font-semibold">{gate.action}</span>
                    <span
                      className={`chip ${
                        gate.decision
                          ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                          : "border-amber-300 bg-amber-50 text-amber-800"
                      }`}
                    >
                      {gate.decision ?? "pending"}
                    </span>
                    <span className="ml-auto font-mono text-[11px] text-ink-faint">
                      run {gate.run_id}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 text-[11px] text-ink-muted">
                    <span>requested {shortTime(gate.requested_at)}</span>
                    <span>deadline {shortTime(gate.deadline)}</span>
                    {gate.approver ? <span>{maskContact(gate.approver)}</span> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <section className="mt-4 grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
        {stages
          .filter((stage) => stage.meaning)
          .map((stage) => (
            <div key={stage.stage} className="card px-4 py-3.5">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${LEVEL_BAR[stage.level]}`} />
                <span className="text-[11.5px] font-semibold uppercase tracking-[0.06em]">
                  {stage.stage.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{stage.meaning}</p>
            </div>
          ))}
      </section>
    </main>
  );
}
