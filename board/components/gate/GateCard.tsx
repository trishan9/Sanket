"use client";

import { AlertTriangle, Check, Clock, ShieldAlert, X } from "lucide-react";
import { useState } from "react";
import { cardSrc, decideGate, type DecisionResult, type PendingGate } from "@/lib/control";

function countdown(seconds: number): string {
  if (seconds <= 0) return "expired";
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds % 60)} s left`;
}

export function GateCard({
  gate,
  approver,
  onDecided,
}: {
  gate: PendingGate;
  approver: string | null;
  onDecided: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<DecisionResult | null>(null);
  const [identity, setIdentity] = useState(approver ?? "");
  const image = cardSrc(gate.image_url);
  const residents = Object.entries(gate.resident_bodies);

  const decide = async (decision: "approved" | "rejected") => {
    setBusy(decision);
    const outcome = await decideGate(gate.run_id, decision, identity.trim());
    setResult(outcome);
    setBusy(null);
    if (!outcome.error) onDecided();
  };

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <div className="label flex items-center gap-1.5">
            <ShieldAlert size={11} /> Awaiting a named officer
          </div>
          <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
            Release {gate.status} to {residents.length} settlements
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="chip">
            <Clock size={11} /> {countdown(gate.seconds_remaining)}
          </span>
          <span className="font-mono text-[11px] text-ink-faint">{gate.run_id}</span>
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[300px_1fr]">
        <div className="border-b p-4 lg:border-b-0 lg:border-r">
          {image ? (
            <img
              src={image}
              alt={`Alert card for ${gate.status}`}
              className="w-full rounded-md border"
            />
          ) : (
            <div className="flex h-64 items-center justify-center rounded-md border text-[12px] text-ink-faint">
              no card rendered
            </div>
          )}
          <p className="mt-2 text-[10.5px] leading-relaxed text-ink-faint">
            This exact image is the WhatsApp attachment. Nothing is re-rendered on release.
          </p>
        </div>

        <div className="p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="stat-box">
              <div className="label">Decision score</div>
              <div className="metric">{gate.decision_score?.toFixed(2) ?? "n/a"}</div>
            </div>
            <div className="stat-box">
              <div className="label">Evidence rows</div>
              <div className="metric">{gate.provenance_links.length}</div>
            </div>
          </div>

          <div className="mt-3">
            <div className="label">What moved the score</div>
            <ul className="mt-1.5 space-y-1">
              {gate.contributions.map((line) => (
                <li key={line} className="font-mono text-[11.5px] text-ink-soft">
                  {line}
                </li>
              ))}
            </ul>
          </div>

          {gate.flip_points.length ? (
            <div className="mt-3">
              <div className="label">Where the decision flips</div>
              <ul className="mt-1.5 space-y-1">
                {gate.flip_points.map((line) => (
                  <li key={line} className="font-mono text-[11.5px] text-ink-soft">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="mt-3">
            <div className="label">Message body sent to institutions</div>
            <p className="mt-1 rounded-md border bg-sunken p-2.5 text-[11.5px] leading-relaxed text-ink-soft">
              {gate.institutional_body}
            </p>
          </div>

          <div className="mt-4 rounded-md border p-3">
            <div className="label">Sign the decision</div>
            <input
              value={identity}
              onChange={(event) => setIdentity(event.target.value)}
              placeholder="approver contact"
              className="field mt-1.5 w-full font-mono text-[12px]"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                onClick={() => void decide("approved")}
                disabled={busy !== null || gate.expired}
                className="btn bg-level-red text-white disabled:opacity-50"
              >
                <Check size={14} /> {busy === "approved" ? "releasing" : "Approve and release"}
              </button>
              <button
                onClick={() => void decide("rejected")}
                disabled={busy !== null || gate.expired}
                className="btn disabled:opacity-50"
              >
                <X size={14} /> Reject
              </button>
            </div>
            <p className="mt-2 text-[10.5px] leading-relaxed text-ink-faint">
              Only the registered approver contact is accepted. Any other value is refused with 403
              and nothing is sent.
            </p>
          </div>

          {result ? (
            <div
              className={`mt-3 rounded-md border p-3 text-[12px] ${
                result.error ? "border-level-red/40 bg-level-red/5" : "bg-sunken"
              }`}
            >
              {result.error ? (
                <div className="flex items-start gap-2 text-level-red">
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                  <span>
                    {result.reason === "unauthorised"
                      ? "Refused. That contact is not the registered approver."
                      : result.error}
                  </span>
                </div>
              ) : (
                <div>
                  <div className="font-medium">
                    {result.decision === "approved"
                      ? `Released to ${result.released?.length ?? 0} recipients`
                      : "Rejected. Nothing was sent."}
                  </div>
                  {result.released?.length ? (
                    <table className="mt-2 w-full text-left text-[11px]">
                      <tbody>
                        {result.released.map((row) => (
                          <tr key={row.message_sid || row.contact} className="border-b last:border-0">
                            <td className="py-1 pr-2 text-ink-muted">{row.settlement}</td>
                            <td className="py-1 pr-2 font-mono">{row.contact}</td>
                            <td className="py-1 pr-2">{row.status}</td>
                            <td className="py-1 font-mono text-ink-faint">{row.message_sid}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
