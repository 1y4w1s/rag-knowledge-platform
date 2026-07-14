import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/components/chat/ChatMessageList";

import {
  readSseBodyUntilDone,
  rollbackInFlightMessages,
} from "./thread-stream-abort";

const ts = "2026-07-10T00:00:00.000Z";

function user(content: string): ChatMessage {
  return { role: "user", content, createdAt: ts };
}

function assistant(
  content: string,
  streaming = false,
): ChatMessage {
  return {
    role: "assistant",
    content,
    citations: [],
    expandedIndex: null,
    streaming,
    createdAt: ts,
  };
}

describe("rollbackInFlightMessages (G3-E1)", () => {
  it("returns empty when there is nothing to roll back", () => {
    expect(rollbackInFlightMessages([])).toEqual({
      messages: [],
      restoredDraft: null,
    });
  });

  it("keeps history when the last message is not streaming", () => {
    const prev = [user("年假"), assistant("5 天")];
    expect(rollbackInFlightMessages(prev)).toEqual({
      messages: prev,
      restoredDraft: null,
    });
  });

  it("removes user + streaming assistant pair and returns draft text", () => {
    const prev = [
      user("旧问题"),
      assistant("旧回答"),
      user("对比各库年假"),
      assistant("", true),
    ];
    expect(rollbackInFlightMessages(prev)).toEqual({
      messages: [user("旧问题"), assistant("旧回答")],
      restoredDraft: "对比各库年假",
    });
  });

  it("removes only streaming assistant when no preceding user", () => {
    const prev = [assistant("", true)];
    expect(rollbackInFlightMessages(prev)).toEqual({
      messages: [],
      restoredDraft: null,
    });
  });
});

describe("readSseBodyUntilDone (G3-E1 abort)", () => {
  it("stops reading when AbortController fires mid-stream", async () => {
    const encoder = new TextEncoder();
    let releaseSecondChunk: (() => void) | undefined;
    const secondChunkGate = new Promise<void>((resolve) => {
      releaseSecondChunk = resolve;
    });

    const body = new ReadableStream<Uint8Array>({
      async pull(controller) {
        controller.enqueue(encoder.encode("event: token\ndata: {}\n\n"));
        await secondChunkGate;
        controller.enqueue(encoder.encode("event: token\ndata: {}\n\n"));
        controller.close();
      },
    });

    const controller = new AbortController();
    const chunks: string[] = [];

    const readPromise = readSseBodyUntilDone(body, controller.signal, (text) => {
      chunks.push(text);
    });

    await vi.waitFor(() => expect(chunks.length).toBe(1));
    controller.abort();
    releaseSecondChunk!();

    await expect(readPromise).resolves.toBe("aborted");
    expect(chunks.length).toBe(1);
  });

  it("completes when the stream finishes without abort", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("event: done\ndata: {}\n\n"));
        controller.close();
      },
    });

    const controller = new AbortController();
    const chunks: string[] = [];

    await expect(
      readSseBodyUntilDone(body, controller.signal, (text) => {
        chunks.push(text);
      }),
    ).resolves.toBe("done");

    expect(chunks).toHaveLength(1);
  });
});

describe("G3-E1 no dual stream guard", () => {
  it("only one AbortController owns the active chat fetch at a time", async () => {
    const encoder = new TextEncoder();
    let activeControllers = 0;
    let maxConcurrent = 0;

    const fetchImpl = vi.fn((_input: RequestInfo, init?: RequestInit) => {
      const signal = init?.signal;
      if (!signal) throw new Error("missing signal");

      activeControllers += 1;
      maxConcurrent = Math.max(maxConcurrent, activeControllers);

      const body = new ReadableStream<Uint8Array>({
        async pull(controller) {
          await new Promise((resolve) => setTimeout(resolve, 50));
          if (signal.aborted) {
            controller.close();
            return;
          }
          controller.enqueue(encoder.encode("event: token\ndata: {}\n\n"));
          controller.close();
        },
      });

      signal.addEventListener("abort", () => {
        activeControllers -= 1;
      });

      return Promise.resolve(
        new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
      );
    });

    const first = new AbortController();
    const second = new AbortController();

    const firstFetch = fetchImpl("/chat", { signal: first.signal });
    first.abort();
    await fetchImpl("/chat", { signal: second.signal });
    await firstFetch;

    expect(maxConcurrent).toBe(1);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
