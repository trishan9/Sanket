"use client";

import { useEffect, useState } from "react";
import { fetchPreparedness } from "@/lib/api";
import type { PreparednessProfile } from "@/lib/types";

export function AmISafe() {
  const [profiles, setProfiles] = useState<PreparednessProfile[]>([]);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    void fetchPreparedness().then((data) => {
      if (!data) return;
      const all = Object.values(data.corridors).flatMap((c) => c.profiles ?? []);
      setProfiles(all);
      setSelected(all[0]?.settlement ?? "");
    });
  }, []);

  const profile = profiles.find((p) => p.settlement === selected);

  return (
    <section className="card card-pad">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
        Am I safe? / म सुरक्षित छु?
      </h2>
      <p className="mt-1 text-xs text-ink-faint">
        Pick a settlement to see its modelled lead time and what that means.
      </p>

      <select
        value={selected}
        onChange={(event) => setSelected(event.target.value)}
        className="mt-3 w-full rounded border border-line bg-surface px-3 py-2 text-sm"
      >
        {profiles.map((p) => (
          <option key={p.settlement} value={p.settlement}>
            {p.settlement}
          </option>
        ))}
        {profiles.length === 0 ? <option value="">Loading…</option> : null}
      </select>

      {profile ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-md border bg-sunken p-3">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold">
                {profile.minimum_lead_time_minutes !== null
                  ? `${profile.minimum_lead_time_minutes.toFixed(0)} min`
                  : "no modelled arrival"}
              </span>
              <span className="text-xs text-ink-faint">shortest modelled lead time</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-700">
              This is the fastest scenario in the grid, not a prediction of what will happen.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-md border bg-sunken p-2">
              <div className="text-lg font-semibold">{profile.population}</div>
              <div className="text-[10px] text-ink-faint">people (modelled)</div>
            </div>
            <div className="rounded-md border bg-sunken p-2">
              <div className="text-lg font-semibold">{profile.buildings}</div>
              <div className="text-[10px] text-ink-faint">buildings</div>
            </div>
            <div className="rounded-md border bg-sunken p-2">
              <div className="text-lg font-semibold">{profile.bridges}</div>
              <div className="text-[10px] text-ink-faint">bridges</div>
            </div>
          </div>

          {profile.single_point_of_failure ? (
            <p className="rounded border border-amber-300 bg-amber-50 p-2 text-[11px] text-amber-900">
              Single point of failure: losing one crossing isolates this settlement.
            </p>
          ) : null}

          <ul className="space-y-1 text-[11px] text-ink-faint">
            <li>· DEM vintage {profile.dem_vintage}</li>
            {(profile.caveats ?? []).map((caveat) => (
              <li key={caveat}>· {caveat}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
