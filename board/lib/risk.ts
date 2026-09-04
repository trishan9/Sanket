const BASE = process.env.NEXT_PUBLIC_SANKET_API ?? "";

export interface BaseRate {
  stratum: string;
  events: number;
  population: number;
  rate_per_lake: number;
  ci_low: number;
  ci_high: number;
  sample_size: number;
  record_period: string;
  caveat: string;
  rendered: string;
}

export interface RiskParameter {
  name: string;
  group: string;
  value: number | null;
  unit: string;
  source: string;
  observable: boolean;
  note: string;
}

export interface SusceptibilityScore {
  node_id: string;
  rank_score: number;
  band: string;
  summary: string;
  base_rates: BaseRate[];
  unobservable_parameters: string[];
  parameters: RiskParameter[];
  frameworks: string[];
  caveats: string[];
}

export interface CascadeStep {
  order: number;
  node_id: string;
  node_type: string;
  mechanism: string;
  confidence: number;
  note: string;
}

export interface CascadePayload {
  origin: string;
  summary: string;
  decay_per_step: number;
  terminal_confidence: number;
  steps: CascadeStep[];
  caveats: string[];
}

export interface ObservabilityPayload {
  catchment: string;
  inventoried_lakes: number;
  below_detection_limit: number;
  below_attention_threshold: number;
  detection_limit_km2: number;
  attention_threshold_km2: number;
  smallest_inventoried_km2: number;
  summary: string;
  caveats: string[];
}

export interface MetPayload {
  date: string;
  rainfall_explains: boolean;
  daily_percentile: number | null;
  daily_mm: number | null;
  monthly_percentile: number | null;
  monthly_mm: number | null;
  antecedent_mm: number;
  antecedent_days: number;
  seasonal_context: string;
  unobserved_layers: string[];
  summary: string;
  caveats: string[];
}

export interface ValidationRow {
  scenario: string;
  reference: string;
  precision: number;
  recall: number;
  iou: number;
  f1: number;
  true_positive: number;
  false_positive: number;
  false_negative: number;
}

export interface ValidationPayload {
  rows: ValidationRow[];
  reading: string;
}

export interface CompletenessPayload {
  tile: string;
  optical: { product: string; by_month: Record<string, number> };
  radar: { product: string; by_month: Record<string, number> };
  note: string;
}

export interface DamagePayload {
  settlement: string;
  depth_m: number;
  damage_fraction: number;
  low_npr: number;
  high_npr: number;
  low_usd: number;
  high_usd: number;
  summary: string;
  assumptions: string[];
  caveats: string[];
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

export function fetchSusceptibility() {
  return getJson<{ count: number; ranked: SusceptibilityScore[] }>("/api/risk/susceptibility");
}

export function fetchCascade(nodeId: string) {
  return getJson<CascadePayload>(`/api/risk/cascade/${encodeURIComponent(nodeId)}`);
}

export function fetchObservability(catchment: string) {
  return getJson<ObservabilityPayload>(`/api/risk/observability/${encodeURIComponent(catchment)}`);
}

export function fetchMet(isoDate: string) {
  return getJson<MetPayload>(`/api/met/${isoDate}`);
}

export function fetchValidation() {
  return getJson<ValidationPayload>("/api/validation");
}

export function fetchCompleteness() {
  return getJson<CompletenessPayload>("/api/completeness");
}

export function fetchDamage(settlement: string, depthM: number, buildings: number, bridges: number) {
  const query = `settlement=${encodeURIComponent(settlement)}&depth_m=${depthM}&buildings=${buildings}&bridges=${bridges}`;
  return getJson<DamagePayload>(`/api/damage?${query}`);
}
