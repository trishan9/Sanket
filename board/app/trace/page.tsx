"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export default function TraceIndexPage() {
  const [runs, setRuns] = useState<string[]>([]);

  useEffect(() => {
    void fetch(`${BASE}/api/runs`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setRuns(d.runs ?? []))
      .catch(() => setRuns([]));
  }, []);

  return (
    <main className="w-full px-7 pb-16">
      <h1 className="text-lg font-semibold">Trace</h1>
      <p className="mt-1 text-xs text-ink-muted">{runs.length} runs recorded.</p>
      <ul className="mt-4 space-y-1">
        {runs
          .slice()
          .reverse()
          .map((run) => (
            <li key={run}>
              <Link
                href={`/trace/${run}`}
                className="block rounded border bg-surface px-3 py-2 text-sm font-mono hover:bg-sunken"
              >
                {run}
              </Link>
            </li>
          ))}
      </ul>
    </main>
  );
}
