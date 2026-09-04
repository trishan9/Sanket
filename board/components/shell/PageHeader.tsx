import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  meta,
  actions,
}: {
  title: string;
  subtitle?: string;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-10 border-b bg-[--surface]/85 backdrop-blur">
      <div className="flex w-full flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="min-w-0">
          <h1 className="truncate text-[19px] font-semibold tracking-[-0.01em]">{title}</h1>
          {subtitle ? (
            <p className="mt-0.5 text-[12.5px] leading-snug text-ink-muted">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {meta}
          {actions}
        </div>
      </div>
    </header>
  );
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="w-full px-7 py-6">{children}</div>;
}
