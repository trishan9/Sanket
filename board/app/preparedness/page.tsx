"use client";

import { AlertTriangle, Building2, Route, Timer, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { DEFAULT_LAYERS, HazardMap } from "@/components/map/HazardMap";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";
import { fetchPreparedness } from "@/lib/api";
import { fetchHotzones, type HotzoneFeature } from "@/lib/ops";
import type { PreparednessProfile } from "@/lib/types";

const LEVEL_BAR: Record<string, string> = {
  NORMAL: "bg-level-green",
  GREEN: "bg-level-green",
  WATCH: "bg-level-yellow",
  YELLOW: "bg-level-yellow",
  ORANGE: "bg-level-orange",
  ALERT: "bg-level-red",
  RED: "bg-level-red",
  INSUFFICIENT: "bg-level-grey",
  GREY: "bg-level-grey",
};

function severityTint(severity: number): string {
  if (severity >= 0.9) return "bg-red-500";
  if (severity >= 0.6) return "bg-orange-500";
  if (severity >= 0.4) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function PreparednessPage() {
  const [profiles, setProfiles] = useState<PreparednessProfile[]>([]);
  const [zones, setZones] = useState<HotzoneFeature[]>([]);
  const [dimension, setDimension] = useState<"2d" | "3d">("2d");
  const [focus, setFocus] = useState<[number, number] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    void fetchPreparedness().then((data) => {
      if (!data) return;
      setProfiles(Object.values(data.corridors).flatMap((c) => c.profiles ?? []));
    });
    void fetchHotzones().then((data) => setZones(data?.features ?? []));
  }, []);

  const ordered = useMemo(
    () =>
      [...profiles].sort(
        (a, b) => (a.minimum_lead_time_minutes ?? 1e9) - (b.minimum_lead_time_minutes ?? 1e9),
      ),
    [profiles],
  );

  const population = profiles.reduce((t, p) => t + (p.population ?? 0), 0);
  const buildings = profiles.reduce((t, p) => t + (p.buildings ?? 0), 0);
  const bridges = profiles.reduce((t, p) => t + (p.bridges ?? 0), 0);
  const isolated = profiles.filter((p) => p.single_point_of_failure).length;
  const active = ordered.find((p) => p.settlement === selected) ?? ordered[0];
  const maxPop = Math.max(1, ...profiles.map((p) => p.population ?? 0));

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Preparedness"
        title="Who is exposed, how long they have, and what cuts them off"
        lede="Exposure counted inside the modelled wet cells, arrival time from the precomputed scenario grid, and the crossings whose loss isolates a settlement long after the water drops."
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
          Icon={Building2}
          tint="amber"
          foot="OSM and HOT footprints"
        />
        <StatCard
          label="Bridges in the reach"
          value={bridges}
          Icon={Route}
          tint="blue"
          foot="loss cuts access after the flood"
        />
        <StatCard
          label="Single point of failure"
          value={isolated}
          Icon={AlertTriangle}
          tint="violet"
          foot="settlements on one crossing"
        />
      </StatRow>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <div className="card overflow-hidden">
          <div className="card-head">
            <div>
              <div className="label">Exposure map</div>
              <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
                Settlements against the modelled reach
              </div>
            </div>
            <div className="flex gap-1 rounded-md border p-1">
              {(["2d", "3d"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setDimension(mode)}
                  className={`rounded px-2.5 py-1 text-[11.5px] font-medium ${
                    dimension === mode ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                  }`}
                >
                  {mode.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <HazardMap
            layers={DEFAULT_LAYERS}
            dimension={dimension}
            focus={focus}
            height={420}
            onSelect={(name) => setSelected(name)}
          />
        </div>

        <Section
          eyebrow="Urgency"
          title="Ranked by shortest arrival"
          note="Lead time is the fastest scenario in the grid on a DEM that predates the event. It ranks urgency, it is not a forecast."
        >
          <ul className="max-h-[420px] overflow-y-auto">
            {ordered.map((profile) => {
              const zone = zones.find((z) => z.properties.name === profile.settlement);
              const level = zone?.properties.level ?? "INSUFFICIENT";
              return (
                <li key={profile.settlement}>
                  <button
                    onClick={() => {
                      setSelected(profile.settlement);
                      if (zone) setFocus(zone.geometry.coordinates);
                    }}
                    className={`flex w-full items-center gap-3 border-b px-5 py-3 text-left transition-colors last:border-0 hover:bg-sunken ${
                      selected === profile.settlement ? "bg-[--accent-soft]" : ""
                    }`}
                  >
                    <span
                      className={`h-8 w-1 shrink-0 rounded-full ${LEVEL_BAR[level] ?? "bg-level-grey"}`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13.5px] font-medium">
                        {profile.settlement}
                      </span>
                      <span className="block text-[11px] text-ink-faint">{profile.district}</span>
                    </span>
                    <span className="w-24 shrink-0">
                      <span className="block h-1.5 overflow-hidden rounded bg-sunken">
                        <span
                          className="block h-full bg-accent"
                          style={{ width: `${((profile.population ?? 0) / maxPop) * 100}%` }}
                        />
                      </span>
                      <span className="mt-1 block text-right font-mono text-[10.5px] text-ink-faint">
                        {(profile.population ?? 0).toLocaleString()}
                      </span>
                    </span>
                    <span className="w-16 shrink-0 text-right font-mono text-[12.5px] font-semibold">
                      {profile.minimum_lead_time_minutes !== null
                        ? `${Math.round(profile.minimum_lead_time_minutes)}m`
                        : "n/a"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </Section>
      </div>

      {active ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Section eyebrow="Selected" title={active.settlement}>
            <div className="grid grid-cols-3 gap-2 px-5 py-4">
              {[
                { label: "people", value: (active.population ?? 0).toLocaleString(), Icon: Users },
                { label: "buildings", value: active.buildings ?? 0, Icon: Building2 },
                { label: "bridges", value: active.bridges ?? 0, Icon: Route },
              ].map((item) => (
                <div key={item.label} className="stat-box text-center">
                  <item.Icon size={15} className="mx-auto text-ink-faint" strokeWidth={1.9} />
                  <div className="mt-1.5 font-mono text-[19px] font-semibold leading-none">
                    {item.value}
                  </div>
                  <div className="mt-1 text-[10px] text-ink-faint">{item.label}</div>
                </div>
              ))}
            </div>
          </Section>

          <Section eyebrow="Timing" title="Arrival window">
            <div className="px-5 py-4">
              <div className="flex items-baseline gap-2">
                <Timer size={16} className="text-ink-faint" strokeWidth={1.9} />
                <span className="font-mono text-[26px] font-semibold leading-none">
                  {active.minimum_lead_time_minutes !== null
                    ? `${Math.round(active.minimum_lead_time_minutes)}`
                    : "n/a"}
                </span>
                <span className="text-[11.5px] text-ink-faint">minutes, fastest scenario</span>
              </div>
              {active.maximum_lead_time_minutes !== null ? (
                <p className="mt-2 text-[12px] text-ink-muted">
                  Slowest modelled arrival {Math.round(active.maximum_lead_time_minutes)} minutes.
                  The spread between the two is the planning window.
                </p>
              ) : null}
              {active.single_point_of_failure ? (
                <p className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-[11.5px] text-amber-900">
                  Single point of failure. Losing one crossing isolates this settlement after the
                  water drops.
                </p>
              ) : null}
            </div>
          </Section>

          <Section eyebrow="Provenance" title="What these numbers rest on">
            <ul className="space-y-1.5 px-5 py-4">
              <li className="text-[11.5px] text-ink-muted">DEM vintage {active.dem_vintage}</li>
              <li className="text-[11.5px] text-ink-muted">
                generated {String(active.generated_as_of).slice(0, 10)}
              </li>
              {(active.caveats ?? []).map((caveat) => (
                <li key={caveat} className="text-[11.5px] leading-snug text-ink-faint">
                  {caveat}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      ) : null}

      <Section
        eyebrow="Hot zones"
        title="Severity by settlement"
        aside={<span className="text-[11px] text-ink-faint">shortest arrival drives severity</span>}
      >
        <div className="grid gap-2 px-5 py-4 sm:grid-cols-2 lg:grid-cols-5">
          {zones.map((zone) => (
            <button
              key={zone.properties.name}
              onClick={() => {
                setSelected(zone.properties.name);
                setFocus(zone.geometry.coordinates);
              }}
              className="rounded-lg border bg-sunken px-3 py-3 text-left transition-shadow hover:shadow-raised"
            >
              <div className="flex items-center justify-between">
                <span className="truncate text-[12.5px] font-medium">{zone.properties.name}</span>
                <span className={`h-2 w-2 rounded-full ${severityTint(zone.properties.severity)}`} />
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded bg-white">
                <div
                  className={`h-full ${severityTint(zone.properties.severity)}`}
                  style={{ width: `${zone.properties.severity * 100}%` }}
                />
              </div>
              <div className="mt-1.5 font-mono text-[10.5px] text-ink-faint">
                {zone.properties.lead_time_minutes !== null
                  ? `${Math.round(zone.properties.lead_time_minutes)} min`
                  : "no modelled arrival"}
              </div>
            </button>
          ))}
        </div>
      </Section>
    </main>
  );
}
