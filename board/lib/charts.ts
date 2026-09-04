export interface LakeAreaObservation {
  acquired: string;
  area_km2: number;
  obscured: boolean;
  cloud_fraction: number;
}

export interface RainfallObservation {
  date: string;
  basin_mean_mm: number;
}

export interface ChartData {
  lake_area_series: { location: string; observations: LakeAreaObservation[] };
  rainfall_series: { month: string; observations: RainfallObservation[] };
  lead_time_distribution: { minutes: number[] };
}

const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export async function fetchCharts(): Promise<ChartData | null> {
  try {
    const response = await fetch(`${BASE}/api/charts`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as ChartData;
  } catch {
    return null;
  }
}

export function histogramBins(values: number[], binCount: number): { bin: string; count: number }[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / binCount || 1;
  const bins = Array.from({ length: binCount }, (_, i) => ({
    bin: `${Math.round(min + i * width)}`,
    count: 0,
  }));
  for (const v of values) {
    const index = Math.min(binCount - 1, Math.floor((v - min) / width));
    const bucket = bins[index];
    if (bucket) bucket.count += 1;
  }
  return bins;
}
