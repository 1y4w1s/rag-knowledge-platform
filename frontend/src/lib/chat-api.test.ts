import { describe, expect, it } from "vitest";

import {
  dispatchChatSseBlock,
  type ApprovalRequiredPayload,
  type ChatStreamHandlers,
  type Citation,
} from "@/lib/chat-api";
import {
  AgentBudgetPayloadSchema,
  ApprovalRequiredPayloadSchema,
  ApprovalStateSchema,
  ChatDonePayloadSchema,
  ChatMessagesResponseSchema,
  CitationResolveResultSchema,
  CitationSchema,
  HistoryMessageSchema,
  ToolResultPayloadSchema,
  ToolStartPayloadSchema,
} from "@/lib/chat-schemas";

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
      onToken: (_text: string) => {},
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
      onToken: (_text: string) => {},
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
      onToken: (_text: string) => {},
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
      onToken: (_text: string) => {
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
      onToken: (text: string) => {
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
      onToken: (_text: string) => {},
      onDone: () => {},
    };

    expect(() => dispatchChatSseBlock("", handlers)).not.toThrow();
    expect(() => dispatchChatSseBlock("   \n  ", handlers)).not.toThrow();
  });
});

// ── Zod 运行时校验 ─────────────────────────────────────

describe("Zod schemas — CitationSchema", () => {
  it("parses a minimal valid citation", () => {
    const r = CitationSchema.safeParse({
      chunk_id: "c1",
      document_id: "d1",
      doc_name: "doc",
      page: null,
      section_title: null,
      excerpt: "text",
    });
    expect(r.success).toBe(true);
  });

  it("parses a full citation with optional fields", () => {
    const r = CitationSchema.safeParse({
      chunk_id: "c1",
      document_id: "d1",
      doc_name: "doc",
      page: 5,
      section_title: "§2",
      excerpt: "text",
      kb_id: "kb1",
      kb_name: "KB",
      source_status: "available",
    });
    expect(r.success).toBe(true);
  });

  it("rejects missing required chunk_id", () => {
    const r = CitationSchema.safeParse({
      document_id: "d1",
      doc_name: "doc",
      excerpt: "text",
      page: null,
      section_title: null,
    });
    expect(r.success).toBe(false);
  });

  it("rejects non-integer page", () => {
    const r = CitationSchema.safeParse({
      chunk_id: "c1",
      document_id: "d1",
      doc_name: "doc",
      page: "abc",
      section_title: null,
      excerpt: "text",
    });
    expect(r.success).toBe(false);
  });

  it("rejects invalid source_status", () => {
    const r = CitationSchema.safeParse({
      chunk_id: "c1",
      document_id: "d1",
      doc_name: "doc",
      page: null,
      section_title: null,
      excerpt: "text",
      source_status: "unknown_status",
    });
    expect(r.success).toBe(false);
  });
});

describe("Zod schemas — SSE payloads", () => {
  it("ChatDonePayloadSchema parses valid payload", () => {
    const r = ChatDonePayloadSchema.safeParse({
      message_id: "m1",
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          doc_name: "doc",
          excerpt: "text",
          page: null,
          section_title: null,
        },
      ],
    });
    expect(r.success).toBe(true);
    expect(r.data!.citations).toHaveLength(1);
  });

  it("ChatDonePayloadSchema requires citations array", () => {
    const r = ChatDonePayloadSchema.safeParse({
      message_id: "m1",
    });
    expect(r.success).toBe(false);
  });

  it("ApprovalRequiredPayloadSchema parses valid payload", () => {
    const r = ApprovalRequiredPayloadSchema.safeParse({
      approval_id: "a1",
      draft_type: "faq",
      filename: "faq.md",
      kb_id: "kb1",
      kb_name: "test",
      draft_preview: "# title",
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          doc_name: "doc",
          excerpt: "text",
          page: null,
          section_title: null,
        },
      ],
      can_adopt: true,
    });
    expect(r.success).toBe(true);
  });

  it("ApprovalRequiredPayloadSchema rejects missing filename", () => {
    const r = ApprovalRequiredPayloadSchema.safeParse({
      approval_id: "a1",
      draft_type: "faq",
      kb_id: "kb1",
      kb_name: "test",
      draft_preview: "# title",
      citations: [],
      can_adopt: true,
    });
    expect(r.success).toBe(false);
  });

  it("ApprovalStateSchema parses valid state", () => {
    const r = ApprovalStateSchema.safeParse({
      approval_id: "a1",
      filename: "faq.md",
      kb_name: "test",
      draft_preview: "# title",
      citations: [],
      can_adopt: true,
      status: "pending",
    });
    expect(r.success).toBe(true);
  });

  it("ApprovalStateSchema rejects invalid status", () => {
    const r = ApprovalStateSchema.safeParse({
      approval_id: "a1",
      filename: "faq.md",
      kb_name: "test",
      draft_preview: "# title",
      citations: [],
      can_adopt: true,
      status: "unknown",
    });
    expect(r.success).toBe(false);
  });

  it("ToolStartPayloadSchema parses valid payload", () => {
    const r = ToolStartPayloadSchema.safeParse({
      step: 1,
      tool: "search",
      args_summary: "query=test",
    });
    expect(r.success).toBe(true);
  });

  it("ToolResultPayloadSchema parses valid payload", () => {
    const r = ToolResultPayloadSchema.safeParse({
      step: 2,
      tool: "search",
      ok: true,
      summary: "found 3 results",
      latency_ms: 150,
    });
    expect(r.success).toBe(true);
    expect(r.data!.capped).toBeUndefined();
  });

  it("AgentBudgetPayloadSchema parses valid payload", () => {
    const r = AgentBudgetPayloadSchema.safeParse({
      steps_used: 3,
      max_steps: 5,
      capped: false,
    });
    expect(r.success).toBe(true);
  });
});

describe("Zod schemas — REST responses", () => {
  it("CitationResolveResultSchema parses valid result", () => {
    const r = CitationResolveResultSchema.safeParse({
      document_id: "d1",
      chunk_id: "c1",
      source_status: "available",
      doc_name: "doc.pdf",
    });
    expect(r.success).toBe(true);
  });

  it("CitationResolveResultSchema allows null doc_name", () => {
    const r = CitationResolveResultSchema.safeParse({
      document_id: "d1",
      chunk_id: "c1",
      source_status: "document_deleted",
      doc_name: null,
    });
    expect(r.success).toBe(true);
  });

  it("HistoryMessageSchema parses valid user message", () => {
    const r = HistoryMessageSchema.safeParse({
      id: "msg1",
      role: "user",
      content: "hello",
      citations: null,
      created_at: "2026-07-14T00:00:00Z",
    });
    expect(r.success).toBe(true);
  });

  it("HistoryMessageSchema parses assistant message with citations", () => {
    const r = HistoryMessageSchema.safeParse({
      id: "msg2",
      role: "assistant",
      content: "answer",
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          doc_name: "doc",
          excerpt: "text",
          page: null,
          section_title: null,
        },
      ],
      created_at: "2026-07-14T00:00:00Z",
    });
    expect(r.success).toBe(true);
  });

  it("HistoryMessageSchema rejects invalid role", () => {
    const r = HistoryMessageSchema.safeParse({
      id: "msg3",
      role: "admin",
      content: "hack",
      citations: null,
      created_at: "2026-07-14T00:00:00Z",
    });
    expect(r.success).toBe(false);
  });

  it("ChatMessagesResponseSchema parses valid response", () => {
    const r = ChatMessagesResponseSchema.safeParse({
      messages: [
        {
          id: "m1",
          role: "user",
          content: "hi",
          citations: null,
          created_at: "2026-07-14T00:00:00Z",
        },
      ],
    });
    expect(r.success).toBe(true);
    expect(r.data!.messages).toHaveLength(1);
  });
});

describe("dispatchChatSseBlock — Zod guards drop invalid data", () => {
  it("drops citation event with missing required fields", () => {
    let citationCalled = false;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {
        citationCalled = true;
      },
      onToken: (_t: string) => {},
      onDone: () => {},
    };

    // Missing excerpt
    const block = `event: citation\ndata: ${JSON.stringify({ chunk_id: "c1", document_id: "d1", doc_name: "doc" })}`;
    dispatchChatSseBlock(block, handlers);
    expect(citationCalled).toBe(false);
  });

  it("drops done event with missing required fields", () => {
    let doneCalled = false;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: (_t: string) => {},
      onDone: () => {
        doneCalled = true;
      },
    };

    // no citations array
    const block = `event: done\ndata: ${JSON.stringify({ message_id: "m1" })}`;
    dispatchChatSseBlock(block, handlers);
    expect(doneCalled).toBe(false);
  });

  it("drops approval_required event with missing required fields", () => {
    let approvalCalled = false;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: (_t: string) => {},
      onDone: () => {},
      onApprovalRequired: () => {
        approvalCalled = true;
      },
    };

    // many fields missing
    const block = `event: approval_required\ndata: ${JSON.stringify({ approval_id: "a1" })}`;
    dispatchChatSseBlock(block, handlers);
    expect(approvalCalled).toBe(false);
  });

  it("still dispatches valid events after invalid ones", () => {
    let citationCount = 0;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {
        citationCount++;
      },
      onToken: (_t: string) => {},
      onDone: () => {},
    };

    // Invalid first — should be silently dropped
    dispatchChatSseBlock(
      `event: citation\ndata: ${JSON.stringify({})}`,
      handlers,
    );
    expect(citationCount).toBe(0);

    // Valid second — should be dispatched
    dispatchChatSseBlock(
      `event: citation\ndata: ${JSON.stringify({
        chunk_id: "c1",
        document_id: "d1",
        doc_name: "doc",
        excerpt: "text",
        page: null,
        section_title: null,
      })}`,
      handlers,
    );
    expect(citationCount).toBe(1);
  });
});
