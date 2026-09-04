import type { Level } from "@/lib/types";

const STYLES: Record<Level, string> = {
  NORMAL: "border-emerald-300 bg-emerald-50 text-emerald-800",
  WATCH: "border-amber-300 bg-amber-50 text-amber-800",
  ALERT: "border-red-300 bg-red-50 text-red-800",
  INSUFFICIENT: "border-line bg-sunken text-ink-muted",
};

const DOT: Record<Level, string> = {
  NORMAL: "bg-level-green",
  WATCH: "bg-level-yellow",
  ALERT: "bg-level-red",
  INSUFFICIENT: "bg-level-grey",
};

export function StatusBadge({ level, size = "md" }: { level: Level; size?: "sm" | "md" }) {
  const scale = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-[12px]";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border font-semibold uppercase tracking-[0.05em] ${scale} ${STYLES[level]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[level]}`} />
      {level}
    </span>
  );
}
