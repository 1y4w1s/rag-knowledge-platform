import { describe, expect, it } from "vitest";

import {
  dispatchChatSseBlock,
  type ApprovalRequiredPayload,
  type ChatStreamHandlers,
  type Citation,
} from "@/lib/chat-api";

function makeCitation(): Citation {
  return {
    chunk_id: "c1",
    document_id: "d1",
    doc_name: "员工手册 v3",
    page: 12,
    section_title: "年假制度",
    excerpt: "员工每年享有 5 天带薪年假...",
  };
}

function makeApprovalPayload(
  overrides: Partial<ApprovalRequiredPayload> = {},
): ApprovalRequiredPayload {
  return {
    approval_id: "a1",
    draft_type: "faq",
    filename: "FAQ_年假.md",
    kb_id: "kb1",
    kb_name: "HR 制度库",
    draft_preview: "## 年假政策\n\n员工每年享有 5 天带薪年假...",
    citations: [makeCitation()],
    can_adopt: true,
    ...overrides,
  };
}

describe("G4-4.3 dispatchChatSseBlock — approval_required", () => {
  it("calls onApprovalRequired with correct payload", () => {
    const payload = makeApprovalPayload();
    let received: ApprovalRequiredPayload | undefined;

    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onApprovalRequired: (p) => {
        received = p;
      },
    };

    const block = `event: approval_required\ndata: ${JSON.stringify(payload)}`;
    dispatchChatSseBlock(block, handlers);

    expect(received).toBeDefined();
    expect(received!.approval_id).toBe("a1");
    expect(received!.filename).toBe("FAQ_年假.md");
    expect(received!.draft_type).toBe("faq");
    expect(received!.kb_name).toBe("HR 制度库");
    expect(received!.can_adopt).toBe(true);
    expect(received!.citations).toHaveLength(1);
  });

  it("handles can_adopt=false for Member role", () => {
    const payload = makeApprovalPayload({ can_adopt: false });
    let received: ApprovalRequiredPayload | undefined;

    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onApprovalRequired: (p) => {
        received = p;
      },
    };

    const block = `event: approval_required\ndata: ${JSON.stringify(payload)}`;
    dispatchChatSseBlock(block, handlers);

    expect(received!.can_adopt).toBe(false);
  });

  it("does not call onApprovalRequired when handler is not provided", () => {
    const payload = makeApprovalPayload();
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
    };

    const block = `event: approval_required\ndata: ${JSON.stringify(payload)}`;
    // Should not throw
    expect(() => dispatchChatSseBlock(block, handlers)).not.toThrow();
  });

  it("does not leak approval payload to other handlers", () => {
    const payload = makeApprovalPayload();
    let approvalCalled = false;
    let tokenCalled = false;

    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {
        tokenCalled = true;
      },
      onDone: () => {},
      onApprovalRequired: () => {
        approvalCalled = true;
      },
    };

    const block = `event: approval_required\ndata: ${JSON.stringify(payload)}`;
    dispatchChatSseBlock(block, handlers);

    expect(approvalCalled).toBe(true);
    expect(tokenCalled).toBe(false);
  });

  it("does not break existing event dispatch (zero regression)", () => {
    let citationCount = 0;
    let tokenText = "";
    let doneCalled = false;

    const handlers: ChatStreamHandlers = {
      onCitation: () => {
        citationCount++;
      },
      onToken: (text) => {
        tokenText += text;
      },
      onDone: () => {
        doneCalled = true;
      },
    };

    // Simulate a normal SSE sequence
    dispatchChatSseBlock(
      `event: citation\ndata: ${JSON.stringify(makeCitation())}`,
      handlers,
    );
    dispatchChatSseBlock(
      `event: token\ndata: ${JSON.stringify({ text: "你好" })}`,
      handlers,
    );
    dispatchChatSseBlock(
      `event: done\ndata: ${JSON.stringify({ message_id: "m1", citations: [] })}`,
      handlers,
    );

    expect(citationCount).toBe(1);
    expect(tokenText).toBe("你好");
    expect(doneCalled).toBe(true);
  });

  it("handles empty block gracefully", () => {
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
    };

    expect(() => dispatchChatSseBlock("", handlers)).not.toThrow();
    expect(() => dispatchChatSseBlock("   \n  ", handlers)).not.toThrow();
  });
});
