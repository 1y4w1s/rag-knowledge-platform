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
  recent_activities: DashboardActivity[];
  golden_hit_rate_percent: number | null;
  golden_baseline_evaluated_at: string | null;
  avg_retrieval_latency_ms: number | null;
  retrieval_latency_sample_count: number;
  document_retry_count_7d: number;
  storage_cleanup_failure_count: number;
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
