import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";
import type { DocumentStatus } from "@/lib/document-api";
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

export type SearchMode = "filename" | "content";

export const SEARCH_PAGE_SIZE = 20;

export interface SearchDocumentItem {
  doc_id: string;
  filename: string;
  file_type: string;
  status: DocumentStatus;
  kb_id: string;
  kb_name: string;
  created_at: string;
  snippet?: string | null;
  page_number?: number | null;
}

export interface SearchDocumentsResponse {
  items: SearchDocumentItem[];
  query: string;
  total: number;
  limit: number;
  offset: number;
  mode: SearchMode;
}

export interface FetchSearchDocumentsParams {
  q: string;
  scope: ScopeFetchOptions;
  mode?: SearchMode;
  limit?: number;
  offset?: number;
  kbId?: string;
}

export async function fetchSearchDocuments(
  params: FetchSearchDocumentsParams,
): Promise<SearchDocumentsResponse | null> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const trimmed = params.q.trim();
  if (trimmed.length < 1) {
    throw new Error("请输入搜索关键词");
  }

  const mode = params.mode ?? "filename";
  const query = new URLSearchParams({ q: trimmed, mode });
  if (params.limit != null) query.set("limit", String(params.limit));
  if (params.offset != null) query.set("offset", String(params.offset));
  if (params.kbId) query.set("kb_id", params.kbId);

  const base = appendScopeQuery(
    `${API_BASE}/search/documents?${query.toString()}`,
    params.scope,
  );

  const res = await fetch(base, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const detail = await readApiErrorDetail(res);
    if (isWorkspaceForbidden(res.status, detail ?? "")) {
      triggerWorkspaceApiReset();
    }
    if (detail) {
      throw new Error(
        normalizeDetailMessage(detail, res.status, "search"),
      );
    }
    throw new Error(
      statusFallbackMessage(res.status, "search") ??
        "搜索失败，请稍后重试",
    );
  }

  const data = (await res.json()) as SearchDocumentsResponse;
  if (isStaleScopeFetch(params.scope)) return null;
  return data;
}
