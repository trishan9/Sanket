"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { type ChartData, fetchCharts, histogramBins } from "@/lib/charts";
import { useLang } from "@/lib/i18n";
import type { RunRecord } from "@/lib/types";

function ChartCard({ title, source, children }: { title: string; source: string; children: React.ReactNode }) {
  return (
    <div className="card p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      <div className="mt-2 h-40">{children}</div>
      <p className="mt-1 text-[10px] text-ink-faint">{source}</p>
    </div>
  );
}

export function Charts({ runs }: { runs: RunRecord[] }) {
  const [data, setData] = useState<ChartData | null>(null);
  const lang = useLang((s) => s.lang);

  useEffect(() => {
    void fetchCharts().then(setData);
  }, []);

  const costHistory = runs
    .slice()
    .reverse()
    .map((r) => ({ run: r.run_id, cost: r.cost_npr, azure: r.tokens_azure, groq: r.tokens_groq }));

  const leadBins = data ? histogramBins(data.lead_time_distribution.minutes, 10) : [];

  return (
    <section className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
      <ChartCard
        title={lang === "ne" ? "ताल क्षेत्रफल, २०१६ देखि" : "Lake area, 2016 to now"}
        source={
          data
            ? `Sentinel-2 L2A / MNDWI, ${data.lake_area_series.location}, ${data.lake_area_series.observations.length} scenes`
            : "loading…"
        }
      >
        {data ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.lake_area_series.observations}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="acquired" hide />
              <YAxis width={36} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0b0f14", border: "1px solid #1e293b" }} />
              <Line type="monotone" dataKey="area_km2" stroke="#38bdf8" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        ) : null}
      </ChartCard>

      <ChartCard
        title={lang === "ne" ? "वर्षा प्रतिशतक" : "Rainfall percentile"}
        source={data ? `CHIRPS preliminary daily, ${data.rainfall_series.month}` : "loading…"}
      >
        {data ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.rainfall_series.observations}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" hide />
              <YAxis width={36} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0b0f14", border: "1px solid #1e293b" }} />
              <Bar dataKey="basin_mean_mm" fill="#a78bfa" />
            </BarChart>
          </ResponsiveContainer>
        ) : null}
      </ChartCard>

      <ChartCard
        title={lang === "ne" ? "पहुँच समय वितरण" : "Lead-time distribution"}
        source={
          data
            ? `Precomputed scenario grid, ${data.lead_time_distribution.minutes.length} settlement-scenarios`
            : "loading…"
        }
      >
        {data ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={leadBins}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="bin" tick={{ fontSize: 9 }} stroke="#64748b" />
              <YAxis width={28} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0b0f14", border: "1px solid #1e293b" }} />
              <Bar dataKey="count" fill="#eab308" />
            </BarChart>
          </ResponsiveContainer>
        ) : null}
      </ChartCard>

      <ChartCard
        title={lang === "ne" ? "एजेन्ट चालन इतिहास" : "Agent run history"}
        source="core.state runs table, real token counts and NPR cost per provider"
      >
        {costHistory.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={costHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="run" hide />
              <YAxis width={36} tick={{ fontSize: 10 }} stroke="#64748b" />
              <Tooltip contentStyle={{ background: "#0b0f14", border: "1px solid #1e293b" }} />
              <Bar dataKey="cost" fill="#16a34a" name="NPR" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-xs text-ink-faint">No runs recorded yet.</p>
        )}
      </ChartCard>
    </section>
  );
}
