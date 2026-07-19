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
import type { KbListSortMode } from "@/lib/kb-list-utils";
import type { WorkspaceId } from "@/lib/workspace-storage";

const API_BASE = "/api/v1";

export const KB_LIST_FETCH_LIMIT = 100;

export interface KnowledgeBaseListQueryOptions {
  limit?: number;
  offset?: number;
  q?: string;
  sort?: KbListSortMode;
}

export interface KnowledgeBaseListResult {
  items: KnowledgeBase[];
  total: number;
  limit: number;
  offset: number;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  owner_user_id: string | null;
  owner_org_id: string | null;
  org_unit_id: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
  processing_count: number;
  failed_count: number;
}

export interface KnowledgeBaseCreateInput {
  name: string;
  description?: string;
  /** 公司公共库显式传 null；省略则由 department_id 默认当前部门 */
  org_unit_id?: string | null;
  workspace?: WorkspaceId;
  departmentId?: string | null;
}

export interface KnowledgeBaseUpdateInput {
  name: string;
  description?: string;
}

async function parseApiError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (isWorkspaceForbidden(res.status, detail ?? "")) {
    triggerWorkspaceApiReset();
  }
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "knowledge-base");
  }
  return (
    statusFallbackMessage(res.status, "knowledge-base") ??
    "请求失败，请稍后重试"
  );
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export function fetchKnowledgeBase(id: string): Promise<KnowledgeBase>;
export function fetchKnowledgeBase(
  id: string,
  scope: ScopeFetchOptions,
): Promise<KnowledgeBase | null>;
export async function fetchKnowledgeBase(
  id: string,
  scope?: ScopeFetchOptions,
): Promise<KnowledgeBase | null> {
  const res = await fetch(
    appendScopeQuery(`${API_BASE}/knowledge-bases/${id}`, scope),
    {
      headers: authHeaders(),
    },
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  const data = (await res.json()) as KnowledgeBase;
  if (scope && isStaleScopeFetch(scope)) return null;
  return data;
}

export function fetchKnowledgeBases(): Promise<KnowledgeBase[]>;
export function fetchKnowledgeBases(
  scope: ScopeFetchOptions,
): Promise<KnowledgeBase[] | null>;
export async function fetchKnowledgeBases(
  scope?: ScopeFetchOptions,
): Promise<KnowledgeBase[] | null> {
  const page = await fetchKnowledgeBasesPage(
    { limit: KB_LIST_FETCH_LIMIT, offset: 0 },
    scope,
  );
  if (page === null) return null;
  return page.items;
}

function appendKnowledgeBaseListParams(
  params: URLSearchParams,
  options: KnowledgeBaseListQueryOptions,
): void {
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  const query = options.q?.trim();
  if (query) {
    params.set("q", query);
  }
  if (options.sort) {
    params.set("sort", options.sort);
  }
}

export function fetchKnowledgeBasesPage(
  options: KnowledgeBaseListQueryOptions,
  scope?: ScopeFetchOptions,
): Promise<KnowledgeBaseListResult | null> {
  const params = new URLSearchParams();
  appendKnowledgeBaseListParams(params, options);
  const query = params.toString();
  const url = appendScopeQuery(
    `${API_BASE}/knowledge-bases${query ? `?${query}` : ""}`,
    scope,
  );
  return fetchKnowledgeBasesPageRaw(url, scope);
}

async function fetchKnowledgeBasesPageRaw(
  url: string,
  scope?: ScopeFetchOptions,
): Promise<KnowledgeBaseListResult | null> {
  const res = await fetch(url, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  const data = (await res.json()) as
    | KnowledgeBaseListResult
    | KnowledgeBase[];
  if (isStaleScopeFetch(scope)) return null;
  if (Array.isArray(data)) {
    return {
      items: data,
      total: data.length,
      limit: data.length,
      offset: 0,
    };
  }
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: typeof data.total === "number" ? data.total : 0,
    limit: typeof data.limit === "number" ? data.limit : 0,
    offset: typeof data.offset === "number" ? data.offset : 0,
  };
}

export async function createKnowledgeBase(
  input: KnowledgeBaseCreateInput,
): Promise<KnowledgeBase> {
  const body: Record<string, string | null> = { name: input.name.trim() };
  if (input.description?.trim()) {
    body.description = input.description.trim();
  }
  if (input.org_unit_id !== undefined) {
    body.org_unit_id = input.org_unit_id;
  }

  const res = await fetch(
    appendScopeQuery(`${API_BASE}/knowledge-bases`, {
      workspace: input.workspace,
      departmentId: input.departmentId,
    }),
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as KnowledgeBase;
}

export async function updateKnowledgeBase(
  id: string,
  input: KnowledgeBaseUpdateInput,
): Promise<KnowledgeBase> {
  const body: Record<string, string> = { name: input.name.trim() };
  if (input.description !== undefined) {
    body.description = input.description.trim();
  }

  const res = await fetch(`${API_BASE}/knowledge-bases/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as KnowledgeBase;
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/knowledge-bases/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await parseApiError(res));
}

/** 库内对话切换器：当前库可能不在部门 scope 列表里，须保证 `<select>` 有对应 option。 */
export function withCurrentKnowledgeBase(
  items: KnowledgeBase[],
  current: KnowledgeBase,
): KnowledgeBase[] {
  if (items.some((kb) => kb.id === current.id)) return items;
  return [current, ...items];
}
