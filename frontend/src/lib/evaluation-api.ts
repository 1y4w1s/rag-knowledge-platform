import { getAccessToken } from "@/lib/auth-storage";
import { normalizeDetailMessage, readApiErrorDetail, statusFallbackMessage } from "@/lib/api-error";

const API_BASE = "/api/v1";

export interface EvaluationRun {
  id: string;
  run_id: string;
  dataset_name: string;
  mode: string;
  git_sha: string | null;
  total_queries: number;
  skipped: number;
  hit_at_1: number | null;
  hit_at_3: number | null;
  hit_at_5: number | null;
  mrr: number | null;
  precision_at_k: number | null;
  recall_at_k: number | null;
  map_score: number | null;
  correct_rejection_rate: number | null;
  generation_correctness: number | null;
  generation_faithfulness: number | null;
  generation_hallucination_rate: number | null;
  generation_citation_accuracy: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  throughput_qps: number | null;
  breakdown_domain: Record<string, any> | null;
  breakdown_type: Record<string, any> | null;
  notes: string | null;
  triggered_by: string | null;
  created_at: string;
}

export interface TrendPoint {
  run_id: string;
  value: number;
  created_at: string;
  triggered_by: string | null;
}

export interface EvaluationTrend {
  dataset: string;
  metric: string;
  total_runs: number;
  points: TrendPoint[];
  average: number;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = getAccessToken();
  return token
    ? { Authorization: "Bearer " + token, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function handleResponse<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await readApiErrorDetail(resp);
    const msg = normalizeDetailMessage(detail || "", resp.status) || statusFallbackMessage(resp.status);
    throw new Error(msg || "请求失败");
  }
  return (await resp.json()) as T;
}

export async function fetchLatestEvaluation(dataset = "golden_qa", mode = "retrieval"): Promise<EvaluationRun | null> {
  const headers = await authHeaders();
  const resp = await fetch(API_BASE + "/evaluations/latest?dataset=" + dataset + "&mode=" + mode, { headers });
  if (resp.status === 404) return null;
  return handleResponse<EvaluationRun | null>(resp);
}

export async function fetchEvaluationTrends(dataset = "golden_qa", metric = "hit_at_3", last = 30): Promise<EvaluationTrend> {
  const headers = await authHeaders();
  const resp = await fetch(API_BASE + "/evaluations/trends?dataset=" + dataset + "&metric=" + metric + "&last=" + last, { headers });
  return handleResponse<EvaluationTrend>(resp);
}

export async function fetchEvaluationRuns(dataset?: string, mode?: string, limit = 20): Promise<EvaluationRun[]> {
  const headers = await authHeaders();
  let url = API_BASE + "/evaluations/runs?limit=" + limit;
  if (dataset) url += "&dataset=" + encodeURIComponent(dataset);
  if (mode) url += "&mode=" + encodeURIComponent(mode);
  const resp = await fetch(url, { headers });
  return handleResponse<EvaluationRun[]>(resp);
}
