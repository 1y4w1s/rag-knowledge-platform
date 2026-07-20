import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock useMessageStream
const mockSendMessage = vi.fn();
const mockAbortStreaming = vi.fn().mockReturnValue(null);
const mockAbortForModeSwitch = vi.fn().mockReturnValue(null);
const mockLoadMessages = vi.fn();
const mockRegenerate = vi.fn();

vi.mock("@/lib/use-message-stream", () => ({
  useMessageStream: () => ({
    historyLoading: false,
    historyError: null,
    streaming: false,
    streamError: null,
    toolSteps: [],
    agentBudget: null,
    streamAbortRef: { current: null },
    sendingRef: { current: false },
    loadMessages: mockLoadMessages,
    sendMessage: mockSendMessage,
    regenerate: mockRegenerate,
    abortStreaming: mockAbortStreaming,
    abortForModeSwitch: mockAbortForModeSwitch,
    toggleCitation: vi.fn(),
  }),
}));

// Mock useThreadList
const mockLoadThreads = vi.fn();
const mockSelectThread = vi.fn();
const mockResetActiveChat = vi.fn();
const mockCreateNewThread = vi.fn().mockResolvedValue({ id: "new-thread", title: "", status: "active", created_at: "", updated_at: "", last_message_at: null });
const mockRenameThread = vi.fn();
const mockArchiveThread = vi.fn();

vi.mock("@/lib/use-thread-list", () => ({
  useThreadList: () => ({
    threads: [],
    threadsLoading: false,
    threadsError: null,
    loadThreads: mockLoadThreads,
    selectThread: mockSelectThread,
    resetActiveChat: mockResetActiveChat,
    createNewThread: mockCreateNewThread,
    renameThread: mockRenameThread,
    archiveThread: mockArchiveThread,
  }),
}));

// Mock useApprovalResolver
vi.mock("@/lib/use-approval-resolver", () => ({
  useApprovalResolver: () => ({
    resolveApproval: vi.fn(),
    resolvingApprovalId: null,
    approvalError: null,
  }),
}));

import { useThreadSession } from "@/lib/use-thread-session";
import type { ThreadContext } from "@/lib/thread-api";

const mockContext: ThreadContext = {
  kind: "workspace",
  scope: { workspace: "personal", expectedGen: 0, getCurrentGeneration: () => 0 },
};

describe("useThreadSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns all required fields", () => {
    const { result } = renderHook(() => useThreadSession(mockContext));

    expect(result.current).toHaveProperty("threads");
    expect(result.current).toHaveProperty("threadsLoading");
    expect(result.current).toHaveProperty("threadsError");
    expect(result.current).toHaveProperty("activeThreadId");
    expect(result.current).toHaveProperty("messages");
    expect(result.current).toHaveProperty("historyLoading");
    expect(result.current).toHaveProperty("historyError");
    expect(result.current).toHaveProperty("streaming");
    expect(result.current).toHaveProperty("streamError");
    expect(result.current).toHaveProperty("toolSteps");
    expect(result.current).toHaveProperty("agentBudget");
    expect(result.current).toHaveProperty("resolvingApprovalId");
    expect(result.current).toHaveProperty("approvalError");
    expect(result.current).toHaveProperty("loadThreads");
    expect(result.current).toHaveProperty("selectThread");
    expect(result.current).toHaveProperty("createNewThread");
    expect(result.current).toHaveProperty("archiveThread");
    expect(result.current).toHaveProperty("renameThread");
    expect(result.current).toHaveProperty("toggleCitation");
    expect(result.current).toHaveProperty("sendMessage");
    expect(result.current).toHaveProperty("regenerate");
    expect(result.current).toHaveProperty("abortStreaming");
    expect(result.current).toHaveProperty("resolveApproval");
  });

  it("sendMessage delegates to useMessageStream", async () => {
    const { result } = renderHook(() => useThreadSession(mockContext));

    await act(async () => {
      await result.current.sendMessage("你好", "fast");
    });

    expect(mockSendMessage).toHaveBeenCalledWith("你好", "fast");
  });

  it("regenerate delegates to useMessageStream", async () => {
    const { result } = renderHook(() => useThreadSession(mockContext));

    await act(async () => {
      await result.current.regenerate(2);
    });

    expect(mockRegenerate).toHaveBeenCalledWith(2);
  });

  it("createNewThread delegates to useThreadList", async () => {
    renderHook(() => useThreadSession(mockContext));

    expect(mockCreateNewThread).toHaveBeenCalled();
  });

  it("initial state has empty threads and null active thread", () => {
    const { result } = renderHook(() => useThreadSession(mockContext));

    expect(result.current.activeThreadId).toBeNull();
    expect(result.current.threads).toEqual([]);
    expect(result.current.threadsLoading).toBe(false);
    expect(result.current.threadsError).toBeNull();
  });
});
