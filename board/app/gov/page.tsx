"use client";

import { CloudRain, Database, Eye, Mountain, Satellite, Target } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CausalGraph } from "@/components/awareness/CausalGraph";
import { GeoLibreEmbed } from "@/components/GeoLibreEmbed";
import { DEFAULT_LAYERS, HazardMap, type MapLayerState } from "@/components/map/HazardMap";
import { CascadeGraph } from "@/components/risk/CascadeGraph";
import { CompletenessHeatmap } from "@/components/risk/CompletenessHeatmap";
import { ScenarioMatrix } from "@/components/risk/ScenarioMatrix";
import { SusceptibilityPanel } from "@/components/risk/SusceptibilityPanel";
import { ValidationPanel } from "@/components/risk/ValidationPanel";
import { SimulationControl } from "@/components/sim/SimulationControl";
import { Hero, Section, StatCard, StatRow } from "@/components/shell/Hero";
import { fetchMet, fetchObservability, type MetPayload, type ObservabilityPayload } from "@/lib/risk";
import { fetchHotzones, fetchNationalRisk, type HotzoneFeature, type NationalRisk } from "@/lib/ops";

const EVENT_DATES = ["2026-08-26", "2025-07-08"];

const BAND_TINT: Record<string, string> = {
  very_high: "bg-red-500",
  high: "bg-orange-500",
  moderate: "bg-amber-500",
  low: "bg-emerald-500",
  not_assessable: "bg-slate-400",
};

export default function GovPage() {
  const [met, setMet] = useState<MetPayload[]>([]);
  const [observability, setObservability] = useState<ObservabilityPayload | null>(null);
  const [national, setNational] = useState<NationalRisk | null>(null);
  const [zones, setZones] = useState<HotzoneFeature[]>([]);
  const [layers, setLayers] = useState<MapLayerState>(DEFAULT_LAYERS);
  const [dimension, setDimension] = useState<"2d" | "3d">("2d");
  const [minSeverity, setMinSeverity] = useState(0);

  useEffect(() => {
    void Promise.all(EVENT_DATES.map(fetchMet)).then((rows) =>
      setMet(rows.filter((r): r is MetPayload => r !== null)),
    );
    void fetchObservability("Koshi").then(setObservability);
    void fetchNationalRisk().then(setNational);
    void fetchHotzones().then((data) => setZones(data?.features ?? []));
  }, []);

  const shown = useMemo(
    () => zones.filter((z) => z.properties.severity >= minSeverity),
    [zones, minSeverity],
  );

  const ruledOut = met.filter((row) => !row.rainfall_explains).length;

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Technical view, risk engine"
        title="Every number, its source, and what it cannot tell you"
        lede="Susceptibility across the full inventory, cascade chains with decaying confidence, the scenario grid, observation completeness and validation against observed flood extent."
      />

      <StatRow>
        <StatCard
          label="Lakes ranked"
          value={national?.ranked_count ?? 0}
          Icon={Target}
          tint="red"
          foot="potentially dangerous glacial lakes"
        />
        <StatCard
          label="Inventoried water bodies"
          value={(observability?.inventoried_lakes ?? 0).toLocaleString()}
          Icon={Database}
          tint="blue"
          foot="Koshi basin, ICIMOD 2015"
        />
        <StatCard
          label="Below detection limit"
          value={observability?.below_detection_limit ?? 0}
          Icon={Eye}
          tint="amber"
          foot={`at or under ${observability?.detection_limit_km2 ?? 0.003} km2`}
        />
        <StatCard
          label="Rainfall ruled out"
          value={`${ruledOut} of ${met.length}`}
          Icon={CloudRain}
          tint="green"
          foot="event dates, CHIRPS climatology"
        />
      </StatRow>

      <div className="mt-4 grid gap-4 xl:grid-cols-[268px_1fr]">
        <aside className="card flex flex-col">
          <div className="border-b px-4 py-3">
            <span className="card-title">Filters</span>
          </div>
          <div className="border-b px-4 py-3">
            <div className="label">View</div>
            <div className="mt-2 grid grid-cols-2 gap-1 rounded-md border p-1">
              {(["2d", "3d"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setDimension(mode)}
                  className={`rounded px-2 py-1.5 text-[12px] font-medium ${
                    dimension === mode ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                  }`}
                >
                  {mode.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="border-b px-4 py-3">
            <div className="label">Layers</div>
            <div className="mt-2 space-y-1">
              {(
                [
                  ["flood", "Modelled flood path"],
                  ["cells", "Priority cells"],
                  ["lakes", "Glacial lakes"],
                  ["settlements", "Settlements"],
                  ["watched", "Watched features"],
                ] as const
              ).map(([key, label]) => (
                <label
                  key={key}
                  className="flex cursor-pointer items-center gap-2.5 rounded px-1 py-1.5 hover:bg-sunken"
                >
                  <input
                    type="checkbox"
                    checked={layers[key]}
                    onChange={(event) => setLayers({ ...layers, [key]: event.target.checked })}
                    className="h-3.5 w-3.5 accent-[--accent]"
                  />
                  <span className="text-[12.5px] text-ink-soft">{label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="border-b px-4 py-3">
            <div className="flex items-baseline justify-between">
              <span className="label">Minimum severity</span>
              <span className="font-mono text-[11px] text-ink-soft">
                {(minSeverity * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={minSeverity * 100}
              onChange={(event) => setMinSeverity(Number(event.target.value) / 100)}
              className="mt-2 w-full accent-[--accent]"
            />
            <p className="mt-1 text-[10.5px] text-ink-faint">
              {shown.length} of {zones.length} hot zones shown
            </p>
          </div>
          <div className="px-4 py-3">
            <div className="label">Susceptibility bands</div>
            <ul className="mt-2 space-y-1.5">
              {Object.entries(national?.bands ?? {}).map(([band, count]) => (
                <li key={band} className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${BAND_TINT[band] ?? "bg-slate-400"}`} />
                  <span className="flex-1 text-[11.5px] capitalize text-ink-soft">
                    {band.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[11.5px] text-ink-muted">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <div className="min-w-0 space-y-4">
          <div className="card overflow-hidden">
            <div className="card-head">
              <div>
                <div className="label">Hot zones</div>
                <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
                  Corridor with modelled reach and exposure
                </div>
              </div>
              <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-faint">
                <Mountain size={13} /> HMA 8 m DEM
              </span>
            </div>
            <HazardMap layers={layers} dimension={dimension} height={430} />
            <div className="grid gap-2 border-t px-5 py-3 sm:grid-cols-3 lg:grid-cols-5">
              {shown.map((zone) => (
                <div key={zone.properties.name} className="stat-box">
                  <div className="flex items-center justify-between">
                    <span className="truncate text-[12px] font-medium">{zone.properties.name}</span>
                    <span className="font-mono text-[10.5px] text-ink-faint">
                      {(zone.properties.severity * 100).toFixed(0)}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded bg-white">
                    <div
                      className="h-full bg-[--red]"
                      style={{ width: `${zone.properties.severity * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <Section
            eyebrow="Meteorological rule-out"
            title="Both events happened on unremarkable rainfall days"
            aside={
              <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-faint">
                <Satellite size={13} /> CHIRPS v2.0
              </span>
            }
            note="That negative result is why every rainfall-threshold system Nepal operates was blind to these events."
          >
            <div className="grid gap-2 px-5 py-4 sm:grid-cols-2">
              {met.map((row) => (
                <div key={row.date} className="rounded-md border bg-sunken p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[13px] font-semibold">{row.date}</span>
                    <span
                      className={`chip ${
                        row.rainfall_explains
                          ? "border-amber-300 bg-amber-50 text-amber-800"
                          : "border-emerald-300 bg-emerald-50 text-emerald-800"
                      }`}
                    >
                      {row.rainfall_explains ? "plausible" : "ruled out"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="font-mono text-[20px] font-semibold">
                      {row.daily_mm !== null
                        ? row.daily_mm.toFixed(1)
                        : (row.monthly_mm ?? 0).toFixed(0)}
                    </span>
                    <span className="text-[11px] text-ink-faint">
                      mm at the{" "}
                      {Math.round(row.daily_percentile ?? row.monthly_percentile ?? 0)}th percentile
                    </span>
                  </div>
                  <p className="mt-1.5 text-[10.5px] text-ink-faint">
                    not observed: {row.unobserved_layers.join(", ")}
                  </p>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        <SusceptibilityPanel />
        <CascadeGraph />
        <div className="grid gap-4 xl:grid-cols-2">
          <ScenarioMatrix />
          <CompletenessHeatmap />
        </div>
        <GeoLibreEmbed />
        <ValidationPanel />
        <SimulationControl />
        <CausalGraph />
      </div>
    </main>
  );
}
