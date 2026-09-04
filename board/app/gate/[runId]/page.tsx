"use client";

import { use, useEffect, useState } from "react";
import { AskPanel } from "@/components/AskPanel";
import { LangToggle } from "@/components/LangToggle";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchGate } from "@/lib/api";
import { t, useLang } from "@/lib/i18n";
import type { GatePayload } from "@/lib/types";

export default function GateDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const [gate, setGate] = useState<GatePayload | null>(null);
  const lang = useLang((s) => s.lang);

  useEffect(() => {
    let active = true;
    const load = async () => {
      const next = await fetchGate(runId);
      if (active) setGate(next);
    };
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [runId]);

  const payload = gate?.payload;

  return (
    <main className="w-full px-7 pb-16">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">
          {t("gate", lang)}, {runId}
        </h1>
        <LangToggle />
      </div>

      {!gate || gate.gate === null ? (
        <p className="mt-4 text-ink-faint">No gate request found for this run.</p>
      ) : (
        <>
          <div className="mt-3 flex items-center gap-3">
            {payload ? <StatusBadge level={payload.status} /> : null}
            <span className="text-sm text-ink-muted">
              decision: {gate.decision} · requested {gate.requested_at} · deadline {gate.deadline}
            </span>
          </div>

          {payload ? (
            <>
              <section className="mt-4 card card-pad">
                <h2 className="text-xs font-semibold uppercase text-ink-faint">Attribution</h2>
                <ul className="mt-1 space-y-1 text-xs font-mono text-ink-soft">
                  {payload.contributions.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-ink-faint">score {payload.decision_score.toFixed(2)}</p>
              </section>

              <section className="mt-4 card card-pad">
                <h2 className="text-xs font-semibold uppercase text-ink-faint">
                  {t("counterfactuals", lang)}
                </h2>
                <ul className="mt-1 space-y-1 text-xs text-ink-soft">
                  {payload.counterfactuals.map((c, i) => (
                    <li key={i}>
                      If {c.change}, status would be <strong>{c.new_status}</strong>.
                    </li>
                  ))}
                </ul>
              </section>

              <section className="mt-4 card card-pad">
                <h2 className="text-xs font-semibold uppercase text-ink-faint">
                  {t("flipPoints", lang)}
                </h2>
                <ul className="mt-1 space-y-1 text-xs text-ink-soft">
                  {payload.flip_points.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </section>

              <section className="mt-4 card card-pad">
                <img
                  src={payload.image_url}
                  alt="before/after"
                  className="max-h-64 w-full rounded object-cover"
                />
                <p className="mt-1 text-[10px] text-ink-faint">
                  Placeholder Vantor scene until the GeoLibre inundation overlay is wired in.
                </p>
              </section>

              <section className="mt-4 card card-pad">
                <h2 className="text-xs font-semibold uppercase text-ink-faint">Reply</h2>
                <p className="mt-1 font-mono text-sm text-sky-400">APPROVE {runId}</p>
                <p className="text-[10px] text-ink-faint">
                  or REJECT {runId}, from the registered approver&apos;s WhatsApp number only.
                </p>
              </section>

              <AskPanel />
            </>
          ) : null}
        </>
      )}
    </main>
  );
}
