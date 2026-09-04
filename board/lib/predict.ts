const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export interface IndicatorSpec {
  key: string;
  label: string;
  likelihood_ratio_present: number;
  likelihood_ratio_absent: number;
  citation: string;
  rationale: string;
}

export interface Reading {
  key: string;
  state: string;
  likelihood_ratio: number;
  log_contribution: number;
  detail: string;
}

export interface HazardPayload {
  node_id: string;
  node_type: string;
  dam_type: string;
  window_days: number;
  prior_probability: number;
  posterior_probability: number;
  credible_interval: [number, number];
  lift: number;
  dominant_indicator: string | null;
  unobserved: string[];
  method: string;
  steps: string[];
  caveats: string[];
  summary: string;
  readings: Reading[];
}

export interface Candidate {
  node_id: string;
  node_type: string;
  steps_downstream: number;
  prior_probability: number;
  posterior_probability: number;
  share: number;
  supporting: string[];
  contradicting: string[];
  unobserved: string[];
  summary: string;
}

export interface RootCausePayload {
  observed_at: string;
  window_days: number;
  summary: string;
  indistinguishable: string[];
  candidates: Candidate[];
  caveats: string[];
}

export interface LadderStage {
  stage: string;
  level: string;
  order: number;
  headline: string;
  headline_nepali: string;
  meaning: string;
  autonomous: boolean;
}

export interface EscalationPayload {
  stage: string;
  level: string;
  previous_stage: string | null;
  autonomous: boolean;
  escalated: boolean;
  changed: boolean;
  headline: string;
  headline_nepali: string;
  meaning: string;
  reason: string;
  at: string;
  summary: string;
}

export type Observations = Record<string, boolean | null>;

function query(observations: Observations): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(observations)) {
    if (value === null) continue;
    parts.push(`${key}=${value ? "true" : "false"}`);
  }
  return parts.join("&");
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

export function fetchIndicators() {
  return getJson<{ indicators: IndicatorSpec[] }>("/api/predict/indicators");
}

export function fetchHazard(
  nodeId: string,
  observations: Observations,
  windowDays: number,
  daysSinceFormation: number,
) {
  const suffix = query(observations);
  return getJson<HazardPayload>(
    `/api/predict/${encodeURIComponent(nodeId)}?window_days=${windowDays}` +
      `&days_since_formation=${daysSinceFormation}${suffix ? `&${suffix}` : ""}`,
  );
}

export function fetchRootCause(
  settlement: string,
  perNode: Record<string, Observations>,
  windowDays: number,
) {
  const parts: string[] = [];
  for (const [nodeId, observations] of Object.entries(perNode)) {
    for (const [key, value] of Object.entries(observations)) {
      if (value === null) continue;
      parts.push(`${nodeId}.${key}=${value ? "true" : "false"}`);
    }
  }
  const suffix = parts.join("&");
  return getJson<RootCausePayload>(
    `/api/rootcause/${encodeURIComponent(settlement)}?window_days=${windowDays}` +
      `${suffix ? `&${suffix}` : ""}`,
  );
}

export function fetchLadder() {
  return getJson<{ stages: LadderStage[] }>("/api/escalation/ladder");
}

export function simulateEscalation(
  indicators: number,
  probability: number,
  verifierPassed: boolean,
  verifierVetoed: boolean,
  previous: string | null,
) {
  const previousPart = previous ? `&previous=${previous}` : "";
  return getJson<EscalationPayload>(
    `/api/escalation/simulate?indicators=${indicators}&probability=${probability}` +
      `&verifier_passed=${verifierPassed}&verifier_vetoed=${verifierVetoed}${previousPart}`,
  );
}
