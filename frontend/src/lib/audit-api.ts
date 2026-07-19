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
  actor_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  kb_id: string | null;
  kb_name: string | null;
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
  actor_user_id?: string;
  ip?: string;
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
  if (query.actor_user_id) params.set("actor_user_id", query.actor_user_id);
  if (query.ip) params.set("ip", query.ip);
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

const DETAIL_KEYS = [
  "filename",
  "name",
  "title",
  "tool",
  "tool_name",
  "email",
  "reason",
  "error",
  "message",
  "role",
] as const;

/** 优先展示可读字段，避免整坨 JSON。 */
export function formatAuditDetails(
  details: Record<string, unknown> | null,
): string {
  if (!details || Object.keys(details).length === 0) return "—";

  for (const key of DETAIL_KEYS) {
    const value = details[key];
    if (typeof value === "string" && value.trim()) return value;
  }

  const pairs: string[] = [];
  for (const [key, value] of Object.entries(details)) {
    if (value == null || key === "seed") continue;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      pairs.push(`${key}=${String(value)}`);
    }
    if (pairs.length >= 3) break;
  }
  if (pairs.length > 0) return pairs.join(" · ");

  try {
    const raw = JSON.stringify(details);
    return raw.length > 80 ? `${raw.slice(0, 77)}…` : raw;
  } catch {
    return "—";
  }
}
