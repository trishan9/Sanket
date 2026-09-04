export type Level = "NORMAL" | "WATCH" | "ALERT" | "INSUFFICIENT";

export type ClaimType =
  | "observation"
  | "correlation"
  | "model_output"
  | "scenario"
  | "hypothesis"
  | "recommendation";

export interface Counterfactual {
  change: string;
  new_status: Level;
  new_lead_time_minutes: number | null;
}

export interface SettlementStatus {
  settlement: string;
  basin_id: string;
  level: Level;
  lead_time_minutes: number | null;
  confidence: string | null;
  run_id: string | null;
  written_at: string;
  evidence: {
    ref?: string;
    claim_type?: ClaimType;
    render_style?: string;
    source?: string;
    method?: string;
    dataset_vintage?: string;
    caveats?: string[];
    value?: Record<string, unknown>;
    decision_score?: number;
    contributions?: string[];
    counterfactuals?: Counterfactual[];
    flip_points?: string[];
    what_would_change_my_mind?: string[];
    public_note_english?: string;
    public_note_nepali?: string;
    vetoed?: boolean;
  };
}

export interface RunRecord {
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
  degradations: string;
}

export interface BoardSnapshot {
  corridor_level: Level;
  settlements: SettlementStatus[];
  runs: RunRecord[];
  last_checked: string | null;
  generated_at: string;
}

export type TraceKind =
  | "TRIGGER"
  | "MEMORY"
  | "WATCH"
  | "STEP"
  | "TOOL"
  | "RETRY"
  | "ERROR"
  | "VERIFY"
  | "EXPLAIN"
  | "ACTION"
  | "GATE"
  | "APPROVED"
  | "REJECTED"
  | "DEGRADED"
  | "DONE";

export interface TraceLine {
  ts: string;
  run_id: string;
  basin_id: string;
  agent: string;
  kind: TraceKind;
  message: string;
  replay: boolean;
  step: number | null;
  tool: string | null;
  args: Record<string, unknown> | null;
  result: string | null;
  provider: string | null;
  model: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_npr: number | null;
  failed: boolean;
}

export interface TracePayload {
  run_id: string;
  lines: TraceLine[];
  rendered: string[];
}

export interface GatePayload {
  run_id: string;
  gate_id?: string;
  decision?: string;
  requested_at?: string;
  deadline?: string;
  payload?: {
    status: Level;
    institutional_body: string;
    resident_bodies: Record<string, string>;
    image_url: string;
    decision_score: number;
    contributions: string[];
    counterfactuals: Counterfactual[];
    flip_points: string[];
    what_would_change_my_mind: string[];
    provenance_links: string[];
  };
  gate?: null;
}

export interface PreparednessProfile {
  settlement: string;
  district: string;
  minimum_lead_time_minutes: number | null;
  maximum_lead_time_minutes: number | null;
  population: number;
  buildings: number;
  bridges: number;
  bridges_at_risk: number;
  single_point_of_failure: boolean;
  dem_vintage: string;
  generated_as_of: string;
  caveats: string[];
}

export interface PreparednessResponse {
  generated_at: string;
  corridors: Record<
    string,
    { available: boolean; reason?: string; basin_id?: string; profiles?: PreparednessProfile[] }
  >;
}
