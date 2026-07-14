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
import type { AgentMode } from "@/lib/agent-mode";
import {
  dispatchChatSseBlock,
  type ChatStreamHandlers,
  type HistoryMessage,
} from "@/lib/chat-api";

const API_BASE = "/api/v1";

export type ThreadStatus = "active" | "archived";

export interface ChatThread {
  id: string;
  title: string;
  status: ThreadStatus;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
}

export interface ChatThreadListResponse {
  threads: ChatThread[];
}

export interface ThreadMessagesResponse {
  messages: HistoryMessage[];
}

export interface ChatThreadPatchBody {
  title?: string;
  status?: ThreadStatus;
}

export type WorkspaceThreadContext = {
  kind: "workspace";
  scope: ScopeFetchOptions;
};

export type KbThreadContext = {
  kind: "knowledge_base";
  kbId: string;
  scope?: Pick<ScopeFetchOptions, "workspace" | "departmentId">;
};

export type ThreadContext = WorkspaceThreadContext | KbThreadContext;

function threadBasePath(context: ThreadContext): string {
  if (context.kind === "workspace") {
    return `${API_BASE}/ask/threads`;
  }
  return `${API_BASE}/knowledge-bases/${context.kbId}/threads`;
}

function scopeQueryOptions(
  context: ThreadContext,
): Pick<ScopeFetchOptions, "workspace" | "departmentId"> {
  if (context.kind === "workspace") {
    return context.scope;
  }
  return context.scope ?? {};
}

function staleScopeOptions(context: ThreadContext): ScopeFetchOptions | undefined {
  if (context.kind === "workspace") {
    return context.scope;
  }
  return undefined;
}

function dispatchSseBlock(block: string, handlers: ChatStreamHandlers): void {
  dispatchChatSseBlock(block, handlers);
}

async function parseThreadApiError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (isWorkspaceForbidden(res.status, detail ?? "")) {
    triggerWorkspaceApiReset();
  }
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return (
    statusFallbackMessage(res.status, "generic") ?? "请求失败，请稍后重试"
  );
}

async function threadFetch(
  context: ThreadContext,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const url = appendScopeQuery(`${threadBasePath(context)}${path}`, scopeQueryOptions(context));
  return fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
}

export async function fetchThreads(
  context: ThreadContext,
  limit = 50,
): Promise<ChatThread[] | null> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await threadFetch(context, `?${params.toString()}`);

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
  }

  const data = (await res.json()) as ChatThreadListResponse;
  const staleScope = staleScopeOptions(context);
  if (staleScope && isStaleScopeFetch(staleScope)) return null;
  return data.threads;
}

export async function createThread(
  context: ThreadContext,
  title = "",
): Promise<ChatThread> {
  const res = await threadFetch(context, "", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
  }

  return (await res.json()) as ChatThread;
}

export async function patchThread(
  context: ThreadContext,
  threadId: string,
  body: ChatThreadPatchBody,
): Promise<ChatThread> {
  const res = await threadFetch(context, `/${threadId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
  }

  return (await res.json()) as ChatThread;
}

export async function deleteThread(
  context: ThreadContext,
  threadId: string,
): Promise<void> {
  const res = await threadFetch(context, `/${threadId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
  }
}

export async function fetchThreadMessages(
  context: ThreadContext,
  threadId: string,
  limit = 50,
): Promise<HistoryMessage[] | null> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await threadFetch(
    context,
    `/${threadId}/messages?${params.toString()}`,
  );

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
  }

  const data = (await res.json()) as ThreadMessagesResponse;
  const staleScope = staleScopeOptions(context);
  if (staleScope && isStaleScopeFetch(staleScope)) return null;
  return data.messages;
}

export async function streamThreadChat(
  context: ThreadContext,
  threadId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
  mode: AgentMode = "fast",
): Promise<void> {
  const res = await threadFetch(context, `/${threadId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, mode }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseThreadApiError(res));
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
      dispatchSseBlock(part, handlers);
    }
  }

  if (buffer.trim()) {
    dispatchSseBlock(buffer, handlers);
  }
}

/** G4-4.3 · Resolve approval (adopt/cancel) via POST /api/v1/agent/approvals/{id}/resolve */
export async function resolveApproval(
  approvalId: string,
  action: "adopt" | "cancel",
): Promise<Record<string, unknown>> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(
    `${API_BASE}/agent/approvals/${encodeURIComponent(approvalId)}/resolve`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action }),
    },
  );

  if (!res.ok) {
    const detail = await readApiErrorDetail(res);
    const message = detail
      ? normalizeDetailMessage(detail, res.status, "generic")
      : (statusFallbackMessage(res.status, "generic") ?? "请求失败，请稍后重试");
    throw new Error(message);
  }

  return (await res.json()) as Record<string, unknown>;
}
