import { describe, expect, it, vi, beforeEach } from "vitest";

import type { ThreadContext } from "@/lib/thread-api";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock auth-storage
vi.mock("@/lib/auth-storage", () => ({
  getAccessToken: () => "mock-token",
}));

// Mock api-error
vi.mock("@/lib/api-error", () => ({
  normalizeDetailMessage: (s: string) => s,
  readApiErrorDetail: async () => "mock error",
  statusFallbackMessage: (s: number) => `Error ${s}`,
}));

// Mock workspace-api-reset
vi.mock("@/lib/workspace-api-reset", () => ({
  isWorkspaceForbidden: () => false,
  triggerWorkspaceApiReset: () => {},
}));

import {
  fetchThreads,
  createThread,
  patchThread,
  deleteThread,
  fetchThreadMessages,
  streamThreadChat,
  deleteThreadMessage,
  type ChatThread,
  type ThreadMessagesResponse,
  type ThreadContext,
} from "@/lib/thread-api";

function makeKbContext(): ThreadContext {
  return {
    kind: "knowledge_base",
    kbId: "kb-123",
    workspace: "personal",
  };
}

function makeMockThread(overrides: Partial<ChatThread> = {}): ChatThread {
  return {
    id: "thread-1",
    title: "年假政策咨询",
    status: "active",
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:05:00Z",
    last_message_at: "2026-07-18T10:05:00Z",
    ...overrides,
  };
}

describe("fetchThreads", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("returns thread list on success", async () => {
    const threads = [makeMockThread(), makeMockThread({ id: "thread-2", title: "加班政策" })];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ threads }),
    });

    const result = await fetchThreads(makeKbContext());
    expect(result).toEqual(threads);
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({}),
    });

    await expect(fetchThreads(makeKbContext())).rejects.toThrow();
  });
});

describe("createThread", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends POST and returns created thread", async () => {
    const thread = makeMockThread();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => thread,
    });

    const result = await createThread(makeKbContext(), "新对话");
    expect(result).toEqual(thread);

    const callUrl = mockFetch.mock.calls[0][0];
    expect(callUrl).toContain("/knowledge-bases/kb-123/threads");

    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(callBody).toEqual({ title: "新对话" });
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(createThread(makeKbContext())).rejects.toThrow();
  });
});

describe("patchThread", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends PATCH with title update", async () => {
    const thread = makeMockThread({ title: "新标题" });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => thread,
    });

    const result = await patchThread(makeKbContext(), "thread-1", { title: "新标题" });
    expect(result.title).toBe("新标题");
    expect(mockFetch.mock.calls[0][1].method).toBe("PATCH");
  });

  it("sends PATCH with archive status", async () => {
    const thread = makeMockThread({ status: "archived" });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => thread,
    });

    const result = await patchThread(makeKbContext(), "thread-1", { status: "archived" });
    expect(result.status).toBe("archived");
  });
});

describe("deleteThread", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends DELETE and returns success", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    await expect(deleteThread(makeKbContext(), "thread-1")).resolves.toBeUndefined();
    expect(mockFetch.mock.calls[0][1].method).toBe("DELETE");
  });

  it("throws on failed delete", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) });

    await expect(deleteThread(makeKbContext(), "thread-1")).rejects.toThrow();
  });
});

describe("fetchThreadMessages", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("returns message array on success", async () => {
    const messages = [
      { id: "m1", role: "user", content: "年假有几天？", created_at: "2026-07-18T10:00:00Z", citations: [] },
      { id: "m2", role: "assistant", content: "5 天", created_at: "2026-07-18T10:00:05Z", citations: [] },
    ];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ messages } satisfies ThreadMessagesResponse),
    });

    const result = await fetchThreadMessages(makeKbContext(), "thread-1");
    expect(result).toEqual(messages);
    expect(result).toHaveLength(2);
  });

  it("returns empty array for KB with no messages", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ messages: [] }),
    });

    const result = await fetchThreadMessages(makeKbContext(), "thread-1");
    expect(result).toEqual([]);
  });
});

describe("deleteThreadMessage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends DELETE for a specific message", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    await expect(
      deleteThreadMessage(makeKbContext(), "thread-1", "message-42"),
    ).resolves.toBeUndefined();

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/thread-1/messages/message-42");
    expect(mockFetch.mock.calls[0][1].method).toBe("DELETE");
  });

  it("throws on non-ok", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) });

    await expect(
      deleteThreadMessage(makeKbContext(), "thread-1", "message-42"),
    ).rejects.toThrow();
  });
});

describe("streamThreadChat", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("sends POST with message and mode", async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("event: token\ndata: {\"text\":\"你好\"}\n\n") })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: { getReader: () => mockReader },
    });

    const handlers = {
      onCitation: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
    };

    await streamThreadChat(makeKbContext(), "thread-1", "你好", handlers);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/thread-1/chat");
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({ message: "你好", mode: "fast" });
    expect(handlers.onToken).toHaveBeenCalledWith("你好");
  });

  it("invokes onDone on done event", async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode("event: done\ndata: {\"message_id\":\"m1\",\"citations\":[]}\n\n") })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      body: { getReader: () => mockReader },
    });

    const handlers = {
      onCitation: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
    };

    await streamThreadChat(makeKbContext(), "thread-1", "年假有几天？", handlers);
    expect(handlers.onDone).toHaveBeenCalledWith({ message_id: "m1", citations: [] });
  });
});
