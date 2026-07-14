import { getAccessToken } from "@/lib/auth-storage";
import {
  appendScopeQuery,
  type ScopeFetchOptions,
} from "@/lib/scope-fetch";

const API_BASE = "/api/v1";

export type CitationLabelMode = "kb" | "workspace";

export interface Citation {
  chunk_id: string;
  document_id: string;
  doc_name: string;
  page: number | null;
  section_title: string | null;
  excerpt: string;
  kb_id?: string | null;
  kb_name?: string | null;
  source_status?: CitationSourceStatus | null;
}

export type CitationSourceStatus =
  | "available"
  | "document_deleted"
  | "chunk_stale"
  | "source_inaccessible";

export const SOURCE_DELETED_LABEL = "源文档已删除";
export const CHUNK_STALE_LABEL = "原文片段已失效（文档已更新）";
export const SOURCE_INACCESSIBLE_LABEL =
  "该引用已不可访问（权限或资料库已变更）";

export interface CitationResolveResult {
  document_id: string;
  chunk_id: string;
  source_status: CitationSourceStatus;
  doc_name: string | null;
}

export interface ChatDonePayload {
  message_id: string;
  citations: Citation[];
  agent_run_id?: string | null;
  approval_id?: string | null;
  approval_status?: string | null;
}

export interface ApprovalRequiredPayload {
  approval_id: string;
  draft_type: string;
  filename: string;
  kb_id: string;
  kb_name: string;
  draft_preview: string;
  citations: Citation[];
  can_adopt: boolean;
}

/** G4-4.2 · 审批卡状态（前端驱动，不落地后端） */
export interface ApprovalState {
  approval_id: string;
  filename: string;
  kb_name: string;
  draft_preview: string;
  citations: Citation[];
  can_adopt: boolean;
  status: "pending" | "adopted" | "cancelled";
}

export interface ChatMessagesResponse {
  messages: HistoryMessage[];
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  /** G4-0.4 / G4-E18: 历史消息附属审批状态（刷新后终态保留） */
  approval_id?: string | null;
  approval_status?: Record<string, unknown> | null;
  created_at: string;
}

export interface ChatStreamHandlers {
  onCitation: (citation: Citation) => void;
  onToken: (text: string) => void;
  onDone: (payload: ChatDonePayload) => void;
  onToolStart?: (payload: import("@/lib/agent-stream").ToolStartPayload) => void;
  onToolResult?: (payload: import("@/lib/agent-stream").ToolResultPayload) => void;
  onAgentBudget?: (payload: import("@/lib/agent-stream").AgentBudgetPayload) => void;
  /** G4-4.3: 编辑模式 SSE approval_required 事件 */
  onApprovalRequired?: (payload: ApprovalRequiredPayload) => void;
}

export function dispatchChatSseBlock(
  block: string,
  handlers: ChatStreamHandlers,
): void {
  if (!block.trim()) return;

  let eventName = "message";
  let dataStr = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event: ")) {
      eventName = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      dataStr = line.slice(6);
    }
  }
  if (!dataStr) return;

  const data = JSON.parse(dataStr) as Record<string, unknown>;
  if (eventName === "citation") {
    handlers.onCitation(data as unknown as Citation);
  } else if (eventName === "token") {
    handlers.onToken(String(data.text ?? ""));
  } else if (eventName === "done") {
    handlers.onDone(data as unknown as ChatDonePayload);
  } else if (eventName === "tool_start") {
    handlers.onToolStart?.({
      step: Number(data.step ?? 0),
      tool: String(data.tool ?? ""),
      args_summary: String(data.args_summary ?? ""),
    });
  } else if (eventName === "tool_result") {
    handlers.onToolResult?.({
      step: Number(data.step ?? 0),
      tool: String(data.tool ?? ""),
      ok: Boolean(data.ok),
      summary: String(data.summary ?? ""),
      latency_ms: Number(data.latency_ms ?? 0),
      capped: data.capped === true ? true : undefined,
    });
  } else if (eventName === "agent_budget") {
    handlers.onAgentBudget?.({
      steps_used: Number(data.steps_used ?? 0),
      max_steps: Number(data.max_steps ?? 5),
      capped: data.capped === true,
    });
  } else if (eventName === "approval_required") {
    handlers.onApprovalRequired?.(data as unknown as ApprovalRequiredPayload);
  }
}

async function parseApiError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as {
      detail?: string | { msg?: string }[];
    };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg ?? "请求参数无效").join("；");
    }
  } catch {
    /* ignore */
  }
  if (res.status === 401) return "登录已过期，请重新登录";
  if (res.status === 403) return "没有权限执行此操作";
  if (res.status === 404) return "资料库不存在";
  return "请求失败，请稍后重试";
}

export function formatCitationLabel(
  citation: Citation,
  mode: CitationLabelMode = "kb",
): string {
  const parts: string[] = [];
  if (mode === "workspace" && citation.kb_name) {
    parts.push(citation.kb_name);
  }
  parts.push(citation.doc_name);
  if (citation.section_title) parts.push(citation.section_title);
  if (citation.page != null) parts.push(`p.${citation.page}`);
  return parts.join(" · ");
}

export function resolveKbIdForCitation(
  pageKbId: string,
  citation: Citation,
): string {
  return citation.kb_id ?? pageKbId;
}

export function isCitationExpandBlocked(citation: Citation): boolean {
  return citation.source_status === "source_inaccessible";
}

export function isCitationChipUnavailable(citation: Citation): boolean {
  return (
    citation.source_status === "source_inaccessible" ||
    citation.source_status === "document_deleted"
  );
}

export function citationChipTitle(citation: Citation): string | undefined {
  if (citation.source_status === "document_deleted") {
    return SOURCE_DELETED_LABEL;
  }
  if (citation.source_status === "source_inaccessible") {
    return SOURCE_INACCESSIBLE_LABEL;
  }
  if (citation.source_status === "chunk_stale") {
    return CHUNK_STALE_LABEL;
  }
  return undefined;
}

export function canLinkToCitationPreview(citation: Citation): boolean {
  return (
    citation.source_status !== "document_deleted" &&
    citation.source_status !== "source_inaccessible"
  );
}

export function isCitationInaccessible(citation: Citation): boolean {
  return citation.source_status === "source_inaccessible";
}

export function previewPathForCitation(
  kbId: string,
  citation: Citation,
): string {
  const base = `/knowledge-bases/${kbId}/documents/${citation.document_id}`;
  if (citation.page != null) return `${base}#page=${citation.page}`;
  return base;
}

export async function resolveCitation(
  kbId: string,
  documentId: string,
  chunkId: string,
  scope?: Pick<ScopeFetchOptions, "workspace" | "departmentId">,
): Promise<CitationResolveResult> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const params = new URLSearchParams({
    document_id: documentId,
    chunk_id: chunkId,
  });
  const url = appendScopeQuery(
    `${API_BASE}/knowledge-bases/${kbId}/citations/resolve?${params}`,
    scope,
  );
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  return (await res.json()) as CitationResolveResult;
}

export async function fetchChatMessages(
  kbId: string,
  limit = 50,
  scope?: Pick<ScopeFetchOptions, "workspace" | "departmentId">,
): Promise<HistoryMessage[]> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const params = new URLSearchParams({ limit: String(limit) });
  const url = appendScopeQuery(
    `${API_BASE}/knowledge-bases/${kbId}/messages?${params}`,
    scope,
  );
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const data = (await res.json()) as ChatMessagesResponse;
  return data.messages;
}

export async function streamChat(
  kbId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
  scope?: Pick<ScopeFetchOptions, "workspace" | "departmentId">,
): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const url = appendScopeQuery(
    `${API_BASE}/knowledge-bases/${kbId}/chat`,
    scope,
  );
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  if (!res.body) {
    throw new Error("服务器未返回流式响应");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      dispatchChatSseBlock(part, handlers);
    }
  }

  if (buffer.trim()) {
    dispatchChatSseBlock(buffer, handlers);
  }
}
