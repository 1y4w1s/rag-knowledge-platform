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
import type {
  ChatDonePayload,
  ChatStreamHandlers,
  HistoryMessage,
} from "@/lib/chat-api";

const API_BASE = "/api/v1";

export interface AskMessagesResponse {
  messages: HistoryMessage[];
}

function dispatchSseBlock(block: string, handlers: ChatStreamHandlers): void {
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
    handlers.onCitation(data as unknown as import("@/lib/chat-api").Citation);
  } else if (eventName === "token") {
    handlers.onToken(String(data.text ?? ""));
  } else if (eventName === "done") {
    handlers.onDone(data as unknown as ChatDonePayload);
  }
}

async function parseAskApiError(res: Response): Promise<string> {
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

export async function fetchAskMessages(
  scope: ScopeFetchOptions,
  limit = 50,
): Promise<HistoryMessage[] | null> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const params = new URLSearchParams({ limit: String(limit) });
  const url = appendScopeQuery(
    `${API_BASE}/ask/messages?${params.toString()}`,
    scope,
  );

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(await parseAskApiError(res));
  }

  const data = (await res.json()) as AskMessagesResponse;
  if (isStaleScopeFetch(scope)) return null;
  return data.messages;
}

export async function streamAskChat(
  message: string,
  handlers: ChatStreamHandlers,
  scope: ScopeFetchOptions,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const url = appendScopeQuery(`${API_BASE}/ask/chat`, scope);
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
    throw new Error(await parseAskApiError(res));
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
