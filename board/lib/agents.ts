const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export interface AgentTool {
  name: string;
  description: string;
  gated: boolean;
}

export interface AgentRouting {
  lane: string;
  model: string;
  provider: string;
  qualified?: string;
  tpm?: number;
  rpm?: number;
}

export interface AgentSpec {
  key: string;
  name: string;
  role: string;
  lane: string;
  fires_when: string;
  inputs: string[];
  outputs: string[];
  tools: AgentTool[];
  autonomy: string;
  uses_model: boolean;
  routing: AgentRouting;
}

export interface AgentsPayload {
  agents: AgentSpec[];
  max_steps: number;
  tool_count: number;
  gated_tools: string[];
  autonomous_ceiling: string;
  tick_seconds: { active: number; standing: number; survey: number };
}

export interface ChainRun {
  run_id: string;
  lines: number;
  agents: string[];
  tools: number;
  started: string | null;
  replay: boolean;
}

export interface TraceLineRow {
  ts: string;
  run_id: string;
  agent: string | null;
  kind: string;
  message: string;
  tool?: string | null;
  args?: Record<string, unknown> | null;
  result?: string | null;
  replay?: boolean;
  failed?: boolean;
  model?: string | null;
  cost_npr?: number | null;
}

export interface ChainTrace {
  run_id: string;
  lines: TraceLineRow[];
  counts_by_agent: Record<string, number>;
  tool_calls: Array<{
    tool: string | null;
    args: Record<string, unknown> | null;
    result: string | null;
    ts: string;
  }>;
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

export function fetchAgents() {
  return getJson<AgentsPayload>("/api/agents");
}

export function fetchChainRuns() {
  return getJson<{ runs: ChainRun[] }>("/api/agents/runs");
}

export function fetchChainTrace(runId: string) {
  return getJson<ChainTrace>(`/api/agents/trace/${encodeURIComponent(runId)}`);
}
