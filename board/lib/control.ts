const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export interface PendingGate {
  gate_id: string;
  run_id: string;
  action: string;
  status: string | null;
  requested_at: string;
  deadline: string;
  seconds_remaining: number;
  expired: boolean;
  decision: string;
  institutional_body: string | null;
  image_url: string | null;
  resident_bodies: Record<string, string>;
  resident_images: Record<string, string>;
  decision_score: number | null;
  contributions: string[];
  counterfactuals: Array<{ change: string; new_status: string; new_lead_time_minutes: number | null }>;
  flip_points: string[];
  what_would_change_my_mind: string[];
  provenance_links: string[];
}

export interface GateQueue {
  approver: string | null;
  pending: PendingGate[];
}

export interface ReleaseRow {
  tier: string;
  contact: string;
  settlement: string;
  status: string;
  message_sid: string;
}

export interface DecisionResult {
  run_id?: string;
  gate_id?: string;
  decision?: string;
  approved_at?: string | null;
  approver?: string;
  released?: ReleaseRow[];
  error?: string;
  reason?: string;
}

export interface DrillState {
  drill_id: string;
  prefix: string;
  state: "running" | "finished" | "failed";
  started_at: string;
  finished_at?: string;
  elapsed_seconds?: number;
  corridor?: string;
  mode?: string;
  ticks?: number;
  investigated?: number;
  handoffs?: number;
  run_ids?: string[];
  latest_run_id?: string | null;
  pending_gates?: PendingGate[];
  error?: string;
}

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function fetchGateQueue(): Promise<GateQueue | null> {
  return getJson<GateQueue>("/api/gate");
}

export function fetchDrill(id: string): Promise<DrillState | null> {
  return getJson<DrillState>(`/api/drill/${id}`);
}

export async function startDrill(instant = false): Promise<DrillState | null> {
  try {
    const response = await fetch(`${BASE}/api/drill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instant }),
      cache: "no-store",
    });
    return (await response.json()) as DrillState;
  } catch {
    return null;
  }
}

export interface DrillAlert {
  run_id?: string;
  settlement?: string;
  level?: string;
  lead_time_minutes?: number | null;
  image_url?: string;
  delivery_status?: string;
  message_sid?: string;
  contact?: string;
  error?: string | null;
}

export async function sendDrillAlert(settlement: string, level: string): Promise<DrillAlert> {
  try {
    const response = await fetch(`${BASE}/api/drill/alert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settlement, level }),
      cache: "no-store",
    });
    return (await response.json()) as DrillAlert;
  } catch (error) {
    return { error: String(error) };
  }
}

export async function decideGate(
  runId: string,
  decision: "approved" | "rejected",
  approver: string,
): Promise<DecisionResult> {
  try {
    const response = await fetch(`${BASE}/api/gate/${runId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, approver }),
      cache: "no-store",
    });
    return (await response.json()) as DecisionResult;
  } catch (error) {
    return { error: String(error) };
  }
}

export function cardSrc(url: string | null): string | null {
  if (!url) return null;
  const marker = "/alertcards/";
  const index = url.indexOf(marker);
  return index === -1 ? url : `${BASE}${url.slice(index)}`;
}
