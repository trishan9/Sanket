"use client";

import { useLang } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type { SettlementStatus } from "@/lib/types";

export function WhyPanel({ status }: { status: SettlementStatus }) {
  const lang = useLang((s) => s.lang);
  const evidence = status.evidence;
  const hasWhy = evidence.contributions && evidence.contributions.length > 0;

  return (
    <section className="mt-4 card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        {t("why", lang)}, {status.settlement}
      </h2>
      {evidence.vetoed ? (
        <p className="mt-2 rounded border border-line bg-[--surface-sunken]/60 px-2 py-1 text-sm text-amber-800">
          {t("vetoed", lang)}
        </p>
      ) : null}
      {!hasWhy ? (
        <p className="mt-2 text-sm text-ink-faint">No decomposition recorded for this status.</p>
      ) : (
        <>
          <ul className="mt-2 space-y-1 text-sm">
            {evidence.contributions!.map((c) => (
              <li key={c} className="font-mono text-xs text-ink-soft">
                {c}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-faint">
            decision score {evidence.decision_score?.toFixed(2) ?? " "}
          </p>
          {evidence.counterfactuals && evidence.counterfactuals.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-ink-faint">
                {t("counterfactuals", lang)}
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-ink-soft">
                {evidence.counterfactuals.map((c, i) => (
                  <li key={i}>
                    If {c.change}, status would be <strong>{c.new_status}</strong>
                    {c.new_lead_time_minutes !== null
                      ? ` (lead ${Math.round(c.new_lead_time_minutes)} min)`
                      : ""}
                    .
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {evidence.flip_points && evidence.flip_points.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-ink-faint">
                {t("flipPoints", lang)}
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-ink-soft">
                {evidence.flip_points.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {evidence.what_would_change_my_mind && evidence.what_would_change_my_mind.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase text-ink-faint">
                {t("whatWouldChangeMyMind", lang)}
              </h3>
              <ul className="mt-1 space-y-1 text-xs text-ink-soft">
                {evidence.what_would_change_my_mind.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="mt-3 text-xs text-ink-faint">
            {lang === "ne" ? evidence.public_note_nepali : evidence.public_note_english}
          </p>
        </>
      )}
    </section>
  );
}
