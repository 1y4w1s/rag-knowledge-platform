import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";

const API_BASE = "/api/v1";

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  kb_id: string | null;
  details: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogQuery {
  limit?: number;
  offset?: number;
  action?: string;
  kb_id?: string;
  created_from?: string;
  created_to?: string;
}

async function parseAuditError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return statusFallbackMessage(res.status) ?? "无法加载审计日志，请稍后重试";
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
}

export async function fetchAuditLogs(
  query: AuditLogQuery = {},
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams();
  if (query.limit != null) params.set("limit", String(query.limit));
  if (query.offset != null) params.set("offset", String(query.offset));
  if (query.action) params.set("action", query.action);
  if (query.kb_id) params.set("kb_id", query.kb_id);
  if (query.created_from) params.set("created_from", query.created_from);
  if (query.created_to) params.set("created_to", query.created_to);

  const qs = params.toString();
  const url = `${API_BASE}/admin/audit-logs${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseAuditError(res));
  return (await res.json()) as AuditLogListResponse;
}

export function formatAuditTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function shortenUuid(id: string | null): string {
  if (!id) return "—";
  return `${id.slice(0, 8)}…`;
}
