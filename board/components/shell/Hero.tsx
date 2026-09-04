import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function Hero({
  eyebrow,
  title,
  lede,
  aside,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-6 pb-7 pt-8">
      <div className="min-w-0 max-w-4xl">
        <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-[--red]">
          {eyebrow}
        </div>
        <h1 className="mt-2.5 text-[38px] font-bold leading-[1.1] tracking-[-0.025em] text-ink">
          {title}
        </h1>
        {lede ? (
          <p className="mt-2.5 max-w-3xl text-[14.5px] leading-relaxed text-ink-soft">{lede}</p>
        ) : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </div>
  );
}

const TINTS: Record<string, string> = {
  red: "bg-red-50 text-red-600 border-red-200",
  amber: "bg-amber-50 text-amber-600 border-amber-200",
  blue: "bg-sky-50 text-sky-600 border-sky-200",
  green: "bg-emerald-50 text-emerald-600 border-emerald-200",
  violet: "bg-violet-50 text-violet-600 border-violet-200",
  slate: "bg-sunken text-ink-muted border-line",
};

export function StatCard({
  label,
  value,
  tint = "slate",
  Icon,
  foot,
}: {
  label: string;
  value: string | number;
  tint?: "red" | "amber" | "blue" | "green" | "violet" | "slate";
  Icon?: LucideIcon;
  foot?: string;
}) {
  return (
    <div className="card flex items-start gap-3 px-4 py-3.5">
      {Icon ? (
        <span
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${TINTS[tint]}`}
        >
          <Icon size={17} strokeWidth={2} />
        </span>
      ) : null}
      <div className="min-w-0">
        <div className="label truncate">{label}</div>
        <div className="mt-1 font-mono text-[25px] font-semibold leading-none tracking-tight">
          {value}
        </div>
        {foot ? <div className="mt-1.5 text-[10.5px] text-ink-faint">{foot}</div> : null}
      </div>
    </div>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>;
}

export function Section({
  title,
  eyebrow,
  aside,
  children,
  note,
}: {
  title: string;
  eyebrow?: string;
  aside?: ReactNode;
  children: ReactNode;
  note?: string;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="card-head">
        <div>
          {eyebrow ? <div className="label">{eyebrow}</div> : null}
          <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">{title}</div>
        </div>
        {aside}
      </div>
      {children}
      {note ? <div className="card-note">{note}</div> : null}
    </section>
  );
}
