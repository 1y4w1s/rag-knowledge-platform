import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";
import {
  isWorkspaceForbidden,
  triggerWorkspaceApiReset,
} from "@/lib/workspace-api-reset";
import {
  appendScopeQuery,
  isStaleScopeFetch,
  type ScopeFetchOptions,
} from "@/lib/scope-fetch";

const API_BASE = "/api/v1";

export interface DocumentStatusCounts {
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}

export interface DashboardActivity {
  type: string;
  title: string;
  kb_id: string;
  doc_id: string | null;
  created_at: string;
}

export interface TrendPoint {
  date: string; // YYYY-MM-DD (UTC)
  count: number;
}

export interface FormatShare {
  format: string;
  count: number;
}

export interface RecentThread {
  id: string;
  title: string;
  kb_id: string | null;
  citation_count: number;
  last_activity_at: string;
}

export interface DashboardStats {
  scope: "personal" | "organization";
  knowledge_base_count: number;
  document_count: number;
  documents_by_status: DocumentStatusCounts;
  total_chunk_count: number;
  avg_processing_duration_seconds: number | null;
  ingestion_success_rate: number | null;
  chat_message_count: number;
  member_count: number | null;
  recent_kb_id: string | null;
  recent_kb_name: string | null;
  recent_activities: DashboardActivity[];
  question_trend: TrendPoint[];
  format_distribution: FormatShare[];
  recent_threads: RecentThread[];
  golden_hit_rate_percent: number | null;
  golden_baseline_evaluated_at: string | null;
  avg_retrieval_latency_ms: number | null;
  retrieval_latency_sample_count: number;
  document_retry_count_7d: number;
  storage_cleanup_failure_count: number;
  usage_7d_user_questions: number;
  usage_7d_assistant_replies: number;
  estimated_api_cost_cny_7d: number | null;
  cost_estimate_note: string | null;
  /** NW-44：当前 CHAT_RETENTION_DAYS；Admin 可见，Member 为 null */
  chat_retention_days: number | null;
  /** NW-46：RATE_LIMIT_BACKEND；Admin 可见，Member 为 null */
  rate_limit_backend: string | null;
  /** NW-46：CITATION_REDACT_ENABLED；Admin 可见，Member 为 null */
  citation_redact_enabled: boolean | null;
  /** NW-46：LLM_CONTEXT_REDACT_ENABLED；Admin 可见，Member 为 null */
  llm_context_redact_enabled: boolean | null;
  /** NW-46：KB_QUOTA_MAX_BYTES（0=关）；Admin 可见，Member 为 null */
  kb_quota_max_bytes: number | null;
}

export function isDashboardEmpty(stats: DashboardStats): boolean {
  return stats.knowledge_base_count === 0 && stats.document_count === 0;
}

export function fetchDashboardStats(): Promise<DashboardStats>;
export function fetchDashboardStats(
  scope: ScopeFetchOptions,
): Promise<DashboardStats | null>;
export async function fetchDashboardStats(
  scope?: ScopeFetchOptions,
): Promise<DashboardStats | null> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(
    appendScopeQuery(`${API_BASE}/dashboard/stats`, scope),
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!res.ok) {
    const detail = await readApiErrorDetail(res);
    if (isWorkspaceForbidden(res.status, detail ?? "")) {
      triggerWorkspaceApiReset();
    }
    if (detail) {
      throw new Error(
        normalizeDetailMessage(detail, res.status, "dashboard"),
      );
    }
    throw new Error(
      statusFallbackMessage(res.status, "dashboard") ??
        "无法加载统计数据，请稍后重试",
    );
  }
  const data = (await res.json()) as DashboardStats;
  if (isStaleScopeFetch(scope)) return null;
  return data;
}
