import { getAccessToken } from "@/lib/auth-storage";
import {
  appendScopeQuery,
  type ScopeFetchOptions,
} from "@/lib/scope-fetch";
import {
  AgentBudgetPayloadSchema,
  ApprovalRequiredPayloadSchema,
  ChatDonePayloadSchema,
  ChatMessagesResponseSchema,
  CitationResolveResultSchema,
  CitationSchema,
  ClarifyPayloadSchema,
  ProposalPreviewPayloadSchema,
  ToolResultPayloadSchema,
  ToolStartPayloadSchema,
} from "@/lib/chat-schemas";
import type { CitationSourceStatus } from "@/lib/citation-status";

export type { CitationSourceStatus } from "@/lib/citation-status";
export {
  canLinkToCitationPreview,
  CHUNK_STALE_CHIP_LABEL,
  CHUNK_STALE_LABEL,
  CITATION_RESOLVE_FAILED_LABEL,
  CITATION_STALE_NOTICE_CHUNK_STALE,
  CITATION_STALE_NOTICE_DELETED,
  CITATION_STALE_NOTICE_INACCESSIBLE,
  citationChipStatusLabel,
  citationChipTitle,
  citationStaleMessageNotice,
  isCitationChipUnavailable,
  isCitationExpandBlocked,
  isCitationInaccessible,
  SOURCE_DELETED_CHIP_LABEL,
  SOURCE_DELETED_LABEL,
  SOURCE_INACCESSIBLE_CHIP_LABEL,
  SOURCE_INACCESSIBLE_LABEL,
} from "@/lib/citation-status";

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
  /** G5 · 文档操作提案转审批后保留 operation，用于终态文案（删除/恢复） */
  operation?: "delete" | "restore";
}

/** G5 · 文档操作提案预览载荷（SSE proposal_preview · 后端不建 pending） */
export interface ProposalPreviewPayload {
  operation: "delete" | "restore";
  document_id: string;
  kb_id: string;
  filename: string;
  kb_name: string;
  impact: string;
  conflict: string | null;
  run_id: string;
  can_adopt: boolean;
  /** B 路径（fast 模式自动识别）需两次点击确认 */
  double_confirm?: boolean;
}

/** G5 · 前端驱动的提案状态（存入 assistant message · 不落地后端） */
export type ProposalState = ProposalPreviewPayload;

/** G5 · 歧义澄清单个候选（SSE clarify · 情景 5） */
export interface ClarifyOption {
  document_id: string;
  filename: string;
  kb_id: string;
}

/** G5 · 歧义澄清载荷（SSE clarify · 用户点选后回 POST clarify 取提案） */
export interface ClarifyPayload {
  operation: "delete" | "restore";
  run_id: string;
  options: ClarifyOption[];
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
  /** 038 · 消息状态 */
  status?: "pending" | "completed" | "interrupted";
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
  /** G5: 文档操作模式 SSE proposal_preview 事件（先提案后确认提交） */
  onProposalPreview?: (payload: ProposalPreviewPayload) => void;
  /** G5: 文档名歧义澄清事件（情景 5 · 多篇命中 → 用户点选） */
  onClarify?: (payload: ClarifyPayload) => void;
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
    const parsed = CitationSchema.safeParse(data);
    if (parsed.success) {
      handlers.onCitation(parsed.data);
    } else {
      console.warn("chat-api: invalid citation SSE data", parsed.error);
    }
  } else if (eventName === "token") {
    handlers.onToken(String(data.text ?? ""));
  } else if (eventName === "done") {
    const parsed = ChatDonePayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onDone(parsed.data);
    } else {
      console.warn("chat-api: invalid done SSE data", parsed.error);
    }
  } else if (eventName === "tool_start") {
    const parsed = ToolStartPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onToolStart?.(parsed.data);
    } else {
      console.warn("chat-api: invalid tool_start SSE data", parsed.error);
    }
  } else if (eventName === "tool_result") {
    const parsed = ToolResultPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onToolResult?.(parsed.data);
    } else {
      console.warn("chat-api: invalid tool_result SSE data", parsed.error);
    }
  } else if (eventName === "agent_budget") {
    const parsed = AgentBudgetPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onAgentBudget?.(parsed.data);
    } else {
      console.warn("chat-api: invalid agent_budget SSE data", parsed.error);
    }
  } else if (eventName === "approval_required") {
    const parsed = ApprovalRequiredPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onApprovalRequired?.(parsed.data);
    } else {
      console.warn(
        "chat-api: invalid approval_required SSE data",
        parsed.error,
      );
    }
  } else if (eventName === "proposal_preview") {
    const parsed = ProposalPreviewPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onProposalPreview?.(parsed.data);
    } else {
      console.warn(
        "chat-api: invalid proposal_preview SSE data",
        parsed.error,
      );
    }
  } else if (eventName === "clarify") {
    const parsed = ClarifyPayloadSchema.safeParse(data);
    if (parsed.success) {
      handlers.onClarify?.(parsed.data);
    } else {
      console.warn("chat-api: invalid clarify SSE data", parsed.error);
    }
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

/** F2：去重后的非空库名（保持首次出现序）。 */
export function distinctCitationKbNames(citations: Citation[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const citation of citations) {
    const name = citation.kb_name?.trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    names.push(name);
  }
  return names;
}

/** F2：≥2 个库时的消息级边界摘要。 */
export function citationKbBoundaryNotice(
  citations: Citation[],
): string | null {
  const names = distinctCitationKbNames(citations);
  if (names.length < 2) return null;
  return `本回答引用：${names.join(" · ")}`;
}

export function resolveKbIdForCitation(
  pageKbId: string,
  citation: Citation,
): string {
  return citation.kb_id ?? pageKbId;
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
  return CitationResolveResultSchema.parse(await res.json());
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
  const data = ChatMessagesResponseSchema.parse(await res.json());
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

export interface SubmitDocumentWriteInput {
  thread_id: string;
  kb_id: string;
  document_id: string;
  operation: "delete" | "restore";
  run_id: string;
}

export interface SubmitDocumentWriteResponse {
  approval_id: string;
  status: string;
}

/** G5 · 确认文档操作提案 → 建 AgentApproval(pending)。 */
export async function submitDocumentWrite(
  input: SubmitDocumentWriteInput,
): Promise<SubmitDocumentWriteResponse> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/agent/document-write/submit`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      thread_id: input.thread_id,
      kb_id: input.kb_id,
      document_id: input.document_id,
      operation: input.operation,
      run_id: input.run_id,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const data = (await res.json()) as SubmitDocumentWriteResponse;
  return data;
}

export interface ClarifyDocumentWriteInput {
  thread_id: string;
  document_id: string;
  operation: "delete" | "restore";
}

/**
 * G5 · 歧义澄清（情景 5）：用户点选目标文档后，回 POST 取回结构化提案（同 proposal_preview）。
 * 返回的 ProposalPreviewPayload 直接驱动提案卡（double_confirm 恒为 true）。
 */
export async function clarifyDocumentWrite(
  input: ClarifyDocumentWriteInput,
): Promise<ProposalPreviewPayload> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/agent/document-write/clarify`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      thread_id: input.thread_id,
      document_id: input.document_id,
      operation: input.operation,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }
  const data = (await res.json()) as ProposalPreviewPayload;
  return data;
}
