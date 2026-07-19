import type { ChatMessage } from "@/components/chat/ChatMessageList";

export interface RollbackInFlightResult {
  messages: ChatMessage[];
  /** User question removed by rollback — restore to input on mode-switch abort. */
  restoredDraft: string | null;
}

/**
 * G3-E1 · Remove the in-flight user + streaming assistant pair after AbortController abort.
 */
export function rollbackInFlightMessages(prev: ChatMessage[]): RollbackInFlightResult {
  if (prev.length === 0) {
    return { messages: prev, restoredDraft: null };
  }
  const last = prev[prev.length - 1];
  if (last?.role !== "assistant" || !("streaming" in last) || !last.streaming) {
    return { messages: prev, restoredDraft: null };
  }
  const withoutAssistant = prev.slice(0, -1);
  const preceding = withoutAssistant[withoutAssistant.length - 1];
  if (preceding?.role === "user") {
    return {
      messages: withoutAssistant.slice(0, -1),
      restoredDraft: preceding.content,
    };
  }
  return { messages: withoutAssistant, restoredDraft: null };
}

/** Read an SSE body until done or aborted (mirrors streamThreadChat loop). */
export async function readSseBodyUntilDone(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal,
  onChunk: (text: string) => void,
): Promise<"done" | "aborted"> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const onAbort = () => {
    void reader.cancel();
  };
  signal.addEventListener("abort", onAbort);

  try {
    while (true) {
      if (signal.aborted) return "aborted";
      const { done, value } = await reader.read();
      if (signal.aborted) return "aborted";
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      onChunk(buffer);
    }
    return "done";
  } catch {
    if (signal.aborted) return "aborted";
    throw new Error("stream read failed");
  } finally {
    signal.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
}
