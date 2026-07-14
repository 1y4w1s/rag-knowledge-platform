import { getAccessToken } from "@/lib/auth-storage";
import {
  getRequestPath,
  isNotFoundDetail,
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";

const API_BASE = "/api/v1";

export type DocumentStatus = "queued" | "processing" | "completed" | "failed";

export interface Document {
  id: string;
  kb_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  uploaded_by: string | null;
  created_at: string;
  updated_at: string;
  visibility: "everyone" | "admin_only";
}

async function authFetch(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  return fetch(url, {
    ...init,
    cache: "no-store",
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
  });
}

const LEGACY_DOCUMENT_API_MSG =
  "接口不存在（请在本机执行 docker compose up -d --build api 更新后端）";

export const SOURCE_DOCUMENT_DELETED_MSG = "源文档已删除";

function isLegacyDocumentMutationPath(requestPath: string): boolean {
  return (
    requestPath.includes("/retry") ||
    /\/documents\/[^/]+$/.test(requestPath)
  );
}

async function parseApiError(res: Response): Promise<string> {
  const requestPath = getRequestPath(res);
  const detail = await readApiErrorDetail(res);

  if (detail) {
    if (
      isNotFoundDetail(detail) &&
      res.status === 404 &&
      isLegacyDocumentMutationPath(requestPath)
    ) {
      return LEGACY_DOCUMENT_API_MSG;
    }
    if (res.status === 404 && requestPath.includes("/preview")) {
      return SOURCE_DOCUMENT_DELETED_MSG;
    }
    return normalizeDetailMessage(detail, res.status, "document");
  }

  if (res.status === 404 && isLegacyDocumentMutationPath(requestPath)) {
    return LEGACY_DOCUMENT_API_MSG;
  }
  if (res.status === 404 && requestPath.includes("/preview")) {
    return SOURCE_DOCUMENT_DELETED_MSG;
  }

  if (res.status === 409) {
    return "资料库中已存在同名文件";
  }

  return (
    statusFallbackMessage(res.status, "document") ?? "请求失败，请稍后重试"
  );
}

export const DOCUMENT_PAGE_SIZE = 50;

export interface DocumentListResult {
  items: Document[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentListQueryOptions {
  limit?: number;
  offset?: number;
  file_type?: string[];
  status?: string[];
  uploaded_from?: string;
  uploaded_to?: string;
}

function appendListQueryParams(
  params: URLSearchParams,
  options: DocumentListQueryOptions,
): void {
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  for (const fileType of options.file_type ?? []) {
    params.append("file_type", fileType);
  }
  for (const status of options.status ?? []) {
    params.append("status", status);
  }
  if (options.uploaded_from) {
    params.set("uploaded_from", options.uploaded_from);
  }
  if (options.uploaded_to) {
    params.set("uploaded_to", options.uploaded_to);
  }
}

function normalizeDocumentListResult(
  body: unknown,
  options: DocumentListQueryOptions,
): DocumentListResult {
  if (Array.isArray(body)) {
    const items = body as Document[];
    return {
      items,
      total: items.length,
      limit: options.limit ?? DOCUMENT_PAGE_SIZE,
      offset: options.offset ?? 0,
    };
  }
  const page = body as Partial<DocumentListResult>;
  const items = Array.isArray(page.items) ? page.items : [];
  return {
    items,
    total: typeof page.total === "number" ? page.total : items.length,
    limit: typeof page.limit === "number" ? page.limit : DOCUMENT_PAGE_SIZE,
    offset: typeof page.offset === "number" ? page.offset : 0,
  };
}

export async function fetchDocumentsPage(
  kbId: string,
  options: DocumentListQueryOptions = {},
): Promise<DocumentListResult> {
  const params = new URLSearchParams();
  appendListQueryParams(params, options);
  const query = params.toString();
  const url = `${API_BASE}/knowledge-bases/${kbId}/documents${
    query ? `?${query}` : ""
  }`;
  const res = await authFetch(url);
  if (!res.ok) throw new Error(await parseApiError(res));
  return normalizeDocumentListResult(await res.json(), options);
}

export async function fetchAllDocuments(
  kbId: string,
  options: Omit<DocumentListQueryOptions, "limit" | "offset"> = {},
): Promise<Document[]> {
  const collected: Document[] = [];
  let offset = 0;
  let total = 0;

  do {
    const page = await fetchDocumentsPage(kbId, {
      ...options,
      limit: DOCUMENT_PAGE_SIZE,
      offset,
    });
    total = page.total;
    collected.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0) break;
  } while (collected.length < total);

  return collected;
}

export async function fetchDocuments(kbId: string): Promise<Document[]> {
  const page = await fetchDocumentsPage(kbId);
  if (page.total <= page.items.length) {
    return page.items;
  }
  return fetchAllDocuments(kbId);
}

export async function uploadDocuments(
  kbId: string,
  files: File[],
): Promise<Document[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await authFetch(`${API_BASE}/knowledge-bases/${kbId}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await parseApiError(res));

  const body = (await res.json()) as { documents: Document[] };
  return body.documents;
}

export function isDocumentProcessing(status: DocumentStatus): boolean {
  return status === "queued" || status === "processing";
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  const res = await authFetch(
    `${API_BASE}/knowledge-bases/${kbId}/documents/${docId}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
}

export async function retryDocument(
  kbId: string,
  docId: string,
): Promise<Document> {
  const res = await authFetch(
    `${API_BASE}/knowledge-bases/${kbId}/documents/${docId}/retry`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return (await res.json()) as Document;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export async function fetchDocument(
  kbId: string,
  docId: string,
): Promise<Document> {
  const res = await authFetch(
    `${API_BASE}/knowledge-bases/${kbId}/documents/${docId}`,
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as Document;
}

export async function fetchDocumentPreview(
  kbId: string,
  docId: string,
): Promise<{ blob: Blob; contentType: string }> {
  const res = await authFetch(
    `${API_BASE}/knowledge-bases/${kbId}/documents/${docId}/preview`,
  );
  if (!res.ok) throw new Error(await parseApiError(res));

  const contentType = res.headers.get("Content-Type") ?? "application/octet-stream";
  const blob = await res.blob();
  return { blob, contentType };
}

export function isPdfPreview(fileType: string, contentType: string): boolean {
  return fileType === "pdf" || contentType.includes("application/pdf");
}

export function isTextPreview(fileType: string, contentType: string): boolean {
  return (
    fileType === "txt" ||
    fileType === "md" ||
    contentType.startsWith("text/")
  );
}

// ── 文档可见性 ─────────────────────────────────────

export async function updateDocumentVisibility(
  kbId: string,
  docId: string,
  visibility: "everyone" | "admin_only",
): Promise<Document> {
  const res = await authFetch(
    `${API_BASE}/knowledge-bases/${kbId}/documents/${docId}/visibility`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visibility }),
    },
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as Document;
}
