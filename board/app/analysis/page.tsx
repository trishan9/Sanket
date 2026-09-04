"use client";

import { useEffect, useState } from "react";
import { CascadeGraph } from "@/components/risk/CascadeGraph";
import { DEFAULT_LAYERS, HazardMap } from "@/components/map/HazardMap";
import { Hero } from "@/components/shell/Hero";
import { IndicatorBoard } from "@/components/predict/IndicatorBoard";
import {
  fetchIndicators,
  fetchRootCause,
  type Candidate,
  type IndicatorSpec,
  type Observations,
  type RootCausePayload,
} from "@/lib/predict";

const SETTLEMENTS = ["Timure", "Syapru Besi", "Dhunche", "Betrawati", "Trishuli Bazaar"];
const SOURCE_NODES = ["lhende_barrier", "purepu_glacier"];

const INITIAL: Record<string, Observations> = {
  lhende_barrier: {
    seismic_landslide_type: true,
    upstream_mass_movement: true,
    radar_water_anomaly: true,
    antecedent_precip_extreme: false,
  },
  purepu_glacier: {
    seismic_landslide_type: false,
    radar_water_anomaly: false,
    lake_area_growth: true,
    antecedent_precip_extreme: false,
  },
};

function CandidateCard({ candidate, rank }: { candidate: Candidate; rank: number }) {
  return (
    <li className="card overflow-hidden">
      <div className="flex items-start gap-4 px-5 py-4">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border bg-sunken font-mono text-[12px] font-semibold">
          {rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-mono text-[14px] font-semibold">{candidate.node_id}</span>
            <span className="text-[11px] uppercase tracking-[0.06em] text-ink-faint">
              {candidate.node_type.replace(/_/g, " ")} · {candidate.steps_downstream} step upstream
            </span>
          </div>

          <div className="mt-2.5 flex items-center gap-3">
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-sunken">
              <div
                className="h-full rounded-full bg-[--red]"
                style={{ width: `${Math.max(1, candidate.share * 100)}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-[13px] font-semibold">
              {(candidate.share * 100).toFixed(0)}%
            </span>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-emerald-700">
                Supports
              </div>
              <ul className="mt-1 space-y-0.5">
                {candidate.supporting.length === 0 ? (
                  <li className="text-[11px] text-ink-faint">none</li>
                ) : (
                  candidate.supporting.map((item) => (
                    <li key={item} className="text-[11px] leading-snug text-ink-soft">
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[--red]">
                Argues against
              </div>
              <ul className="mt-1 space-y-0.5">
                {candidate.contradicting.length === 0 ? (
                  <li className="text-[11px] text-ink-faint">none</li>
                ) : (
                  candidate.contradicting.map((item) => (
                    <li key={item} className="text-[11px] leading-snug text-ink-soft">
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-ink-faint">
                Could not observe
              </div>
              <ul className="mt-1 space-y-0.5">
                {candidate.unobserved.length === 0 ? (
                  <li className="text-[11px] text-ink-faint">none</li>
                ) : (
                  candidate.unobserved.map((item) => (
                    <li key={item} className="text-[11px] leading-snug text-ink-faint">
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}

export default function AnalysisPage() {
  const [indicators, setIndicators] = useState<IndicatorSpec[]>([]);
  const [perNode, setPerNode] = useState<Record<string, Observations>>(INITIAL);
  const [activeNode, setActiveNode] = useState(SOURCE_NODES[0] as string);
  const [settlement, setSettlement] = useState(SETTLEMENTS[0] as string);
  const [result, setResult] = useState<RootCausePayload | null>(null);
  const [dimension, setDimension] = useState<"2d" | "3d">("2d");

  useEffect(() => {
    void fetchIndicators().then((data) => setIndicators(data?.indicators ?? []));
  }, []);

  useEffect(() => {
    void fetchRootCause(settlement, perNode, 7).then(setResult);
  }, [settlement, perNode]);

  return (
    <main className="w-full px-7 pb-16">
      <Hero
        eyebrow="Root-cause attribution"
        title="Which source upstream is consistent with what we saw"
        lede="Walk the drainage graph backwards from an observation and weigh every candidate source on the evidence that supports it, argues against it, or was never observable."
      />

      <div className="card flex flex-wrap items-center gap-3 px-5 py-3.5">
        <span className="label">Observation at</span>
        <div className="flex flex-wrap gap-1 rounded-md border p-1">
          {SETTLEMENTS.map((item) => (
            <button
              key={item}
              onClick={() => setSettlement(item)}
              className={`rounded px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
                settlement === item ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.4fr]">
        <div className="card overflow-hidden">
          <div className="card-head">
            <div>
              <div className="label">Source geography</div>
              <div className="mt-0.5 text-[16px] font-semibold tracking-[-0.01em]">
                Where the candidates sit
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
            focus={[85.377, 28.271]}
            height={330}
          />
        </div>

        <div className="min-w-0">
      {result ? (
        <div
          className={`card px-5 py-4 ${
            result.indistinguishable.length > 0 ? "border-amber-300 bg-amber-50" : ""
          }`}
        >
          <div className="label">Finding</div>
          <p className="mt-1.5 text-[15px] leading-relaxed">{result.summary}</p>
        </div>
      ) : null}

      <ul className="mt-3 space-y-3">
        {(result?.candidates ?? []).map((candidate, index) => (
          <CandidateCard key={candidate.node_id} candidate={candidate} rank={index + 1} />
        ))}
      </ul>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <div className="card mb-3 flex flex-wrap items-center gap-3 px-5 py-3">
            <span className="label">Evidence at</span>
            <div className="flex gap-1 rounded-md border p-1">
              {SOURCE_NODES.map((item) => (
                <button
                  key={item}
                  onClick={() => setActiveNode(item)}
                  className={`rounded px-3 py-1.5 font-mono text-[12px] font-medium transition-colors ${
                    activeNode === item ? "bg-accent text-white" : "text-ink-muted hover:bg-sunken"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
          <IndicatorBoard
            indicators={indicators}
            observations={perNode[activeNode] ?? {}}
            onChange={(next) => setPerNode({ ...perNode, [activeNode]: next })}
          />
        </div>
        <CascadeGraph />
      </div>

      {result ? (
        <div className="card card-note mt-4 rounded-lg">
          <ul className="space-y-1">
            {result.caveats.map((caveat) => (
              <li key={caveat}>· {caveat}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </main>
  );
}
