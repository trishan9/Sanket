import type { BoardSnapshot, GatePayload, PreparednessResponse, TracePayload } from "./types";

const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export async function fetchSnapshot(): Promise<BoardSnapshot | null> {
  try {
    const response = await fetch(`${BASE}/api/status`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as BoardSnapshot;
  } catch {
    return null;
  }
}

export async function fetchProgress(): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(`${BASE}/api/progress`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function ageLabel(iso: string | null): string {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
  if (seconds < 90) return `${Math.round(seconds)} s ago`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  return `${Math.round(seconds / 3600)} h ago`;
}

export interface NationalSummary {
  basins_swept: number;
  tier_counts: Record<string, number>;
  last_swept_at: string | null;
  basins: Array<{ basin_id: string; tier: string; score: number; drivers: string }>;
}

export async function fetchNational(): Promise<NationalSummary | null> {
  try {
    const response = await fetch(`${BASE}/api/national`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as NationalSummary;
  } catch {
    return null;
  }
}

export async function fetchTrace(runId: string): Promise<TracePayload | null> {
  try {
    const response = await fetch(`${BASE}/api/trace/${runId}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as TracePayload;
  } catch {
    return null;
  }
}

export async function fetchGate(runId: string): Promise<GatePayload | null> {
  try {
    const response = await fetch(`${BASE}/api/gate/${runId}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as GatePayload;
  } catch {
    return null;
  }
}

export async function fetchPreparedness(): Promise<PreparednessResponse | null> {
  try {
    const response = await fetch(`${BASE}/api/preparedness`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as PreparednessResponse;
  } catch {
    return null;
  }
}

export async function askSandbox(question: string): Promise<{ answer: string; code: string } | null> {
  try {
    const response = await fetch(`${BASE}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) return null;
    return (await response.json()) as { answer: string; code: string };
  } catch {
    return null;
  }
}
