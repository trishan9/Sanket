import type { SettlementStatus } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

function leadLabel(minutes: number | null): string {
  if (minutes === null) return " ";
  if (minutes < 90) return `${Math.round(minutes)}`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h${String(Math.round(minutes % 60)).padStart(2, "0")}`;
}

function leadUnit(minutes: number | null): string {
  if (minutes === null) return "no modelled arrival";
  return minutes < 90 ? "minutes lead time" : "lead time";
}

export function SettlementTile({
  status,
  selected = false,
}: {
  status: SettlementStatus;
  selected?: boolean;
}) {
  const claim = status.evidence.claim_type ?? "model_output";
  return (
    <div
      className={`card h-full overflow-hidden transition-shadow ${
        selected ? "ring-2 ring-accent" : "hover:shadow-raised"
      }`}
    >
      <div className={`claim-${claim} px-4 py-3.5`}>
        <div className="flex items-start justify-between gap-2">
          <span className="truncate text-[14px] font-semibold">{status.settlement}</span>
          <StatusBadge level={status.level} size="sm" />
        </div>
        <div className="mt-3 flex items-baseline gap-1.5">
          <span className="metric">{leadLabel(status.lead_time_minutes)}</span>
          <span className="text-[11px] text-ink-faint">{leadUnit(status.lead_time_minutes)}</span>
        </div>
      </div>
      <div className="flex items-center justify-between border-t bg-sunken px-4 py-2 text-[11px] text-ink-muted">
        <span>confidence {status.confidence ?? " "}</span>
        <span className="text-ink-faint">{claim.replace("_", " ")}</span>
      </div>
    </div>
  );
}
