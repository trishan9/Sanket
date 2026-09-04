"use client";

import { useLang } from "@/lib/i18n";

export function LangToggle() {
  const { lang, toggle } = useLang();
  return (
    <button
      onClick={toggle}
      className="rounded border border-line bg-[--surface-sunken]/60 px-2 py-1 text-xs font-medium text-ink-soft hover:bg-sunken"
    >
      {lang === "en" ? "नेपाली" : "English"}
    </button>
  );
}
