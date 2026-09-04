const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export interface NotificationRow {
  notification_id: string;
  settlement: string;
  channel: string;
  contact: string;
  sent_at: string | null;
  run_id: string | null;
  delivery_status: string;
  approved_by: string | null;
}

export interface GateRow {
  gate_id: string;
  run_id: string;
  action: string;
  requested_at: string;
  deadline: string;
  approved_at: string | null;
  approver: string | null;
  decision: string | null;
}

export interface RunRow {
  run_id: string;
  basin_id: string;
  agent: string;
  trigger: string;
  mode: string;
  started: string;
  ended: string | null;
  steps: number;
  tokens_azure: number;
  tokens_groq: number;
  cost_npr: number;
  outcome: string | null;
  degradations: string[];
}

export interface StatusRow {
  settlement: string;
  basin_id: string;
  level: string;
  lead_time_minutes: number | null;
  confidence: string | null;
  written_at: string;
  run_id: string | null;
}

export interface AlertHistory {
  stages: Array<{
    stage: string;
    level: string;
    order: number;
    headline: string;
    headline_nepali: string;
    meaning: string;
    autonomous: boolean;
  }>;
  notifications: NotificationRow[];
  gates: GateRow[];
  runs: RunRow[];
  statuses: StatusRow[];
  last_heartbeat: { basin_id: string; at: string; note: string } | null;
  channel_counts: Record<string, number>;
  current_levels: Record<string, string>;
}

export interface HotzoneFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    name: string;
    district: string;
    level: string;
    lead_time_minutes: number | null;
    confidence: string | null;
    severity: number;
  };
}

export interface NationalRisk {
  ranked_count: number;
  bands: Record<string, number>;
  top: Array<{ node_id: string; band: string; rank_score: number }>;
  observability: {
    inventoried_lakes: number;
    below_detection_limit: number;
    detection_limit_km2: number;
  };
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

export function fetchAlertHistory() {
  return getJson<AlertHistory>("/api/alerts/history");
}

export function fetchHotzones() {
  return getJson<{ features: HotzoneFeature[] }>("/api/hotzones");
}

export function fetchNationalRisk() {
  return getJson<NationalRisk>("/api/national-risk");
}
