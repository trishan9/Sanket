"use client";

import { Home, Split, Timer, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { DEFAULT_LAYERS, HazardMap, type MapLayerState } from "@/components/map/HazardMap";
import { Hero, StatCard, StatRow } from "@/components/shell/Hero";
import { StatusBadge } from "@/components/StatusBadge";
import { WhyPanel } from "@/components/WhyPanel";
import { AmISafe } from "@/components/sim/AmISafe";
import { CausalGraph } from "@/components/awareness/CausalGraph";
import { MeasuresPanel } from "@/components/awareness/MeasuresPanel";
import { fetchPreparedness, fetchSnapshot } from "@/lib/api";
import type { BoardSnapshot, PreparednessProfile } from "@/lib/types";

const POLL_MS = 5000;

const LAYER_META: Array<{ key: keyof MapLayerState; label: string; swatch: string }> = [
  { key: "flood", label: "Modelled flood path", swatch: "#2781d6" },
  { key: "cells", label: "Priority cells", swatch: "#d93a4e" },
  { key: "lakes", label: "Glacial lakes (ICIMOD)", swatch: "#0ea5e9" },
  { key: "settlements", label: "Settlements", swatch: "#b31b28" },
  { key: "watched", label: "Watched features", swatch: "#f59e0b" },
];

function leadCell(minutes: number | null): string {
  if (minutes === null) return " ";
  return minutes < 90 ? `${Math.round(minutes)} min` : `${(minutes / 60).toFixed(1)} h`;
}

export default function BoardPage() {
  const [snapshot, setSnapshot] = useState<BoardSnapshot | null>(null);
  const [profiles, setProfiles] = useState<PreparednessProfile[]>([]);
  const [layers, setLayers] = useState<MapLayerState>(DEFAULT_LAYERS);
  const [dimension, setDimension] = useState<"2d" | "3d">("2d");
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const load = () => void fetchSnapshot().then(setSnapshot);
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    void fetchPreparedness().then((data) => {
      if (!data) return;
      setProfiles(Object.values(data.corridors).flatMap((c) => c.profiles ?? []));
    });
  }, []);

  const rows = useMemo(() => {
    const byName = new Map(profiles.map((p) => [p.settlement, p]));
    return (snapshot?.settlements ?? [])
      .map((s) => ({ status: s, profile: byName.get(s.settlement) }))
      .filter((row) => row.status.settlement.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => (a.status.lead_time_minutes ?? 1e9) - (b.status.lead_time_minutes ?? 1e9));
  }, [snapshot, profiles, query]);

  const population = profiles.reduce((total, p) => total + (p.population ?? 0), 0);
  const buildings = profiles.reduce((total, p) => total + (p.buildings ?? 0), 0);
  const isolated = profiles.filter((p) => p.single_point_of_failure).length;
  const shortest = rows[0]?.status.lead_time_minutes ?? null;
  const selectedStatus =
    snapshot?.settlements.find((s) => s.settlement === selected) ?? snapshot?.settlements[0];

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Bhotekoshi-Trishuli corridor · standing watch"
        title="What is moving upstream, and who is below it"
        lede="Continuous radar and optical watch over the corridor, with modelled arrival times for every settlement downstream of the barrier."
      />

      <StatRow>
        <StatCard
          label="People downstream"
          value={population.toLocaleString()}
          Icon={Users}
          tint="red"
          foot="WorldPop modelled residence"
        />
        <StatCard
          label="Buildings exposed"
          value={buildings.toLocaleString()}
          Icon={Home}
          tint="amber"
          foot="OSM / HOT footprints"
        />
        <StatCard
          label="Shortest lead time"
          value={shortest !== null ? `${Math.round(shortest)}` : " "}
          Icon={Timer}
          tint="blue"
          foot="minutes, fastest scenario in grid"
        />
        <StatCard
          label="Isolation risk"
          value={isolated}
          Icon={Split}
          tint="slate"
          foot="settlements on a single crossing"
        />
      </StatRow>

      <div className="mt-4 grid gap-4 lg:grid-cols-[264px_1fr]">
        <aside className="card flex flex-col">
          <div className="border-b px-4 py-3">
            <div className="flex items-baseline justify-between">
              <span className="card-title">Explore</span>
              <button
                onClick={() => {
                  setLayers(DEFAULT_LAYERS);
                  setDimension("2d");
                  setQuery("");
                }}
                className="text-[11px] font-semibold text-[--red] hover:underline"
              >
                Reset
              </button>
            </div>
          </div>

          <div className="border-b px-4 py-3">
            <div className="label">View</div>
            <div className="mt-2 grid grid-cols-2 gap-1 rounded-md border p-1">
              {(["2d", "3d"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setDimension(mode)}
                  className={`rounded px-2 py-1.5 text-[12px] font-medium transition-colors ${
                    dimension === mode ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                  }`}
                >
                  {mode.toUpperCase()}
                </button>
              ))}
            </div>
            {dimension === "3d" ? (
              <p className="mt-2 text-[10.5px] text-ink-faint">
                Terrain exaggeration ×1.6, shown on the map badge.
              </p>
            ) : null}
          </div>

          <div className="border-b px-4 py-3">
            <div className="label">Map layers</div>
            <div className="mt-2 space-y-1">
              {LAYER_META.map((item) => (
                <label
                  key={item.key}
                  className="flex cursor-pointer items-center gap-2.5 rounded px-1 py-1.5 hover:bg-sunken"
                >
                  <input
                    type="checkbox"
                    checked={layers[item.key]}
                    onChange={(event) =>
                      setLayers({ ...layers, [item.key]: event.target.checked })
                    }
                    className="h-3.5 w-3.5 accent-[--accent]"
                  />
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: item.swatch }}
                  />
                  <span className="text-[12.5px] text-ink-soft">{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="px-4 py-3">
            <div className="label">Find settlement</div>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
              className="field mt-2"
            />
          </div>
        </aside>

        <HazardMap
          layers={layers}
          dimension={dimension}
          height={560}
          onSelect={(name) => setSelected(name)}
        />
      </div>

      <section className="card mt-4 overflow-hidden">
        <div className="card-head">
          <div>
            <div className="label">Downstream of the barrier</div>
            <div className="mt-0.5 text-[17px] font-semibold tracking-[-0.01em]">
              Ranked by arrival time
            </div>
          </div>
          <span className="text-[11px] text-ink-faint">{rows.length} settlements</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[13px]">
            <thead>
              <tr className="border-b bg-sunken">
                <th className="px-5 py-2.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Settlement
                </th>
                <th className="px-3 py-2.5 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  District
                </th>
                <th className="px-3 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  People
                </th>
                <th className="px-3 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Buildings
                </th>
                <th className="px-3 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Bridges
                </th>
                <th className="px-3 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Lead time
                </th>
                <th className="px-5 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ status, profile }) => (
                <tr
                  key={status.settlement}
                  onClick={() => setSelected(status.settlement)}
                  className={`cursor-pointer border-b transition-colors last:border-0 hover:bg-sunken ${
                    selected === status.settlement ? "bg-[--accent-soft]" : ""
                  }`}
                >
                  <td className="px-5 py-3 font-medium">
                    {status.settlement}
                    {profile?.single_point_of_failure ? (
                      <span className="mt-0.5 block text-[10.5px] font-semibold text-amber-700">
                        Single crossing
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-3 text-ink-muted">{profile?.district ?? " "}</td>
                  <td className="px-3 py-3 text-right font-mono">
                    {profile?.population?.toLocaleString() ?? " "}
                  </td>
                  <td className="px-3 py-3 text-right font-mono">{profile?.buildings ?? " "}</td>
                  <td className="px-3 py-3 text-right font-mono">{profile?.bridges ?? " "}</td>
                  <td className="px-3 py-3 text-right">
                    <span className="inline-block rounded bg-red-50 px-2 py-1 font-mono text-[12px] font-semibold text-red-700">
                      {leadCell(status.lead_time_minutes)}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    <StatusBadge level={status.level} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-note">
          Lead times are the fastest arrival across the precomputed scenario grid on a DEM that
          predates the event. They rank urgency; they are not a forecast.
        </div>
      </section>

      {selectedStatus ? (
        <div className="mt-4">
          <WhyPanel status={selectedStatus} />
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <AmISafe />
        <MeasuresPanel />
      </div>

      <div className="mt-4">
        <CausalGraph />
      </div>
    </main>
  );
}
