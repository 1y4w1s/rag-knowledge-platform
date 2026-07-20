import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ChatPageShell } from "@/components/chat/ChatPageShell";
import type { ChatMessage, UserChatMessage, AssistantChatMessage } from "@/components/chat/ChatMessageList";

vi.mock("@/components/chat/ThreadListPanel", () => ({
  ThreadListPanel: ({ onCreateThread }: { onCreateThread: () => void }) => (
    <div data-testid="thread-list-panel">
      <button data-testid="new-chat-btn" onClick={onCreateThread}>ÃÃÂ½Â¨Â¶ÃÂ»Â°</button>
    </div>
  ),
}));

vi.mock("@/components/chat/ChatMessageList", () => ({
  ChatMessageList: ({ messages, onRegenerate }: { messages: ChatMessage[]; onRegenerate?: (idx: number) => void }) => (
    <div data-testid="chat-message-list">
      {messages.map((m, i) => (
        <div key={i} data-testid={`msg-${i}`}>
          {m.role === "user" ? `ÃÃÂ»Â§: ${m.content}` : `ÃÃºÃÃ: ${m.content}`}
          {m.role === "assistant" && onRegenerate && (
            <button data-testid={`regenerate-${i}`} onClick={() => onRegenerate(i)}>ÃÃÃÃÃÃºÂ³Ã</button>
          )}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/chat/ChatInput", () => ({
  ChatInput: ({ onSend, disabled }: { onSend: (msg: string) => void; disabled?: boolean }) => (
    <div data-testid="chat-input">
      <input data-testid="msg-input" disabled={disabled} />
      <button data-testid="send-btn" onClick={() => { if (!disabled) onSend("ÃÃ£ÂºÃ"); }}>Â·Â¢ÃÃ</button>
    </div>
  ),
}));

vi.mock("@/components/chat/ChatLoadingPanel", () => ({
  ChatLoadingPanel: () => <div data-testid="loading-panel">Â¼ÃÃÃÃÃ...</div>,
}));

vi.mock("@/components/chat/AgentModeSwitcher", () => ({
  AgentModeSwitcher: () => <div data-testid="agent-switcher" />,
}));

vi.mock("@/components/chat/AgentBudgetChip", () => ({
  AgentBudgetChip: () => <div data-testid="agent-budget" />,
}));

vi.mock("@/components/chat/ToolTimeline", () => ({
  ToolTimeline: () => <div data-testid="tool-timeline" />,
}));

function makeUserMsg(overrides: Partial<UserChatMessage> = {}): UserChatMessage {
  return { role: "user", content: "ÃÃªÂ¼ÃÃÃÂ¼Â¸ÃÃ¬Â£Â¿", createdAt: "2026-07-18T10:00:00Z", ...overrides };
}

function makeAssistantMsg(overrides: Partial<AssistantChatMessage> = {}): AssistantChatMessage {
  return {
    role: "assistant", content: "5 ÃÃ¬", citations: [], expandedIndex: null,
    createdAt: "2026-07-18T10:00:05Z", streaming: false, ...overrides,
  };
}

const defaultThreadPanel = {
  collapsed: false, className: "", onDismiss: vi.fn(), threads: [],
  activeThreadId: null, threadsLoading: false, threadsError: null,
  creatingThread: false, archivingThreadId: null,
  onSelectThread: vi.fn(), onCreateThread: vi.fn(),
  onArchiveThread: vi.fn(), onRetryThreads: vi.fn(),
};

const defaultAgentConfig = { mode: "fast" as const, budget: null, onChange: vi.fn() };
const defaultChatState = {
  messages: [] as ChatMessage[], historyLoading: false, historyError: null,
  streamError: null, streaming: false, toolSteps: [], loadMessages: vi.fn(),
};
const defaultMessageListConfig = {
  kbId: "kb-1", onToggleCitation: vi.fn(), onAdoptApproval: vi.fn(),
  onCancelApproval: vi.fn(), resolvingApprovalId: null, approvalError: null,
};
const defaultInputConfig = { disabled: false, onSend: vi.fn(), draftRestore: undefined };
const defaultToolbar = <div />;

describe("ChatPageShell", () => {
  it("renders thread panel, message list and chat input", () => {
    render(
      <ChatPageShell
        threadPanel={defaultThreadPanel}
        agentConfig={defaultAgentConfig}
        chatState={defaultChatState}
        messageListConfig={defaultMessageListConfig}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      >
        <div data-testid="extra-content">Â¶Ã®ÃÃ¢ÃÃÃÃ</div>
      </ChatPageShell>,
    );
    expect(screen.getByTestId("thread-list-panel")).toBeTruthy();
    expect(screen.getByTestId("chat-message-list")).toBeTruthy();
    expect(screen.getByTestId("chat-input")).toBeTruthy();
    expect(screen.getByTestId("extra-content")).toBeTruthy();
  });

  it("shows loading panel when historyLoading is true", () => {
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: true }}
        agentConfig={defaultAgentConfig}
        chatState={{ ...defaultChatState, historyLoading: true }}
        messageListConfig={defaultMessageListConfig}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    expect(screen.getByTestId("loading-panel")).toBeTruthy();
  });

  it("displays messages passed in chatState", () => {
    const messages: ChatMessage[] = [makeUserMsg(), makeAssistantMsg()];
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: true }}
        agentConfig={defaultAgentConfig}
        chatState={{ ...defaultChatState, messages }}
        messageListConfig={{ ...defaultMessageListConfig, onRegenerate: vi.fn() }}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    expect(screen.getByText("ÃÃÂ»Â§: ÃÃªÂ¼ÃÃÃÂ¼Â¸ÃÃ¬Â£Â¿")).toBeTruthy();
    expect(screen.getByText("ÃÃºÃÃ: 5 ÃÃ¬")).toBeTruthy();
  });

  it("regenerate button calls onRegenerate callback", () => {
    const onRegenerate = vi.fn();
    const messages: ChatMessage[] = [makeUserMsg(), makeAssistantMsg({ id: "msg-2" })];
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: true }}
        agentConfig={defaultAgentConfig}
        chatState={{ ...defaultChatState, messages }}
        messageListConfig={{ ...defaultMessageListConfig, onRegenerate }}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    fireEvent.click(screen.getByTestId("regenerate-1"));
    expect(onRegenerate).toHaveBeenCalledWith(1);
  });

  it("new chat button calls onCreateThread", () => {
    const onCreateThread = vi.fn();
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: false, onCreateThread }}
        agentConfig={defaultAgentConfig}
        chatState={defaultChatState}
        messageListConfig={defaultMessageListConfig}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    fireEvent.click(screen.getByTestId("new-chat-btn"));
    expect(onCreateThread).toHaveBeenCalled();
  });

  it("shows error banner when streamError is set", () => {
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: true }}
        agentConfig={defaultAgentConfig}
        chatState={{ ...defaultChatState, historyError: "Â¼ÃÃÃÃÂ§Â°Ã", streamError: "Â¶ÃÂ»Â°Â³Ã¶Â´Ã­" }}
        messageListConfig={defaultMessageListConfig}
        inputConfig={defaultInputConfig}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    expect(screen.getByText("Â¶ÃÂ»Â°Â³Ã¶Â´Ã­")).toBeTruthy();
    expect(screen.getByText("Â¼ÃÃÃÃÂ§Â°Ã")).toBeTruthy();
  });

  it("disables input when disabled is true", () => {
    const onSend = vi.fn();
    render(
      <ChatPageShell
        threadPanel={{ ...defaultThreadPanel, collapsed: true }}
        agentConfig={defaultAgentConfig}
        chatState={defaultChatState}
        messageListConfig={defaultMessageListConfig}
        inputConfig={{ disabled: true, onSend, draftRestore: undefined }}
        toolbar={defaultToolbar}
        scrollRef={{ current: null }}
      />,
    );
    const sendBtn = screen.getByTestId("send-btn");
    fireEvent.click(sendBtn);
    expect(onSend).not.toHaveBeenCalled();
  });
});
