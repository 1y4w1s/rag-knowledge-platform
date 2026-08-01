import { describe, expect, it, vi } from "vitest";

import {
  clarifyDocumentWrite,
  dispatchChatSseBlock,
  submitDocumentWrite,
  type ChatStreamHandlers,
  type ClarifyPayload,
  type ProposalPreviewPayload,
} from "@/lib/chat-api";

function makeProposal(
  overrides: Partial<ProposalPreviewPayload> = {},
): ProposalPreviewPayload {
  return {
    operation: "delete",
    document_id: "d1",
    kb_id: "kb1",
    filename: "员工手册 v3.pdf",
    kb_name: "HR 制度库",
    impact: "该文档将被移入回收站，引用它的对话将标记为来源不可访问。",
    conflict: null,
    run_id: "r1",
    can_adopt: true,
    ...overrides,
  };
}

describe("G5 dispatchChatSseBlock — proposal_preview", () => {
  it("calls onProposalPreview with correct payload", () => {
    const payload = makeProposal();
    let received: ProposalPreviewPayload | undefined;

    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onProposalPreview: (p) => {
        received = p;
      },
    };

    const block = `event: proposal_preview\ndata: ${JSON.stringify(payload)}`;
    dispatchChatSseBlock(block, handlers);

    expect(received).toBeDefined();
    expect(received!.operation).toBe("delete");
    expect(received!.document_id).toBe("d1");
    expect(received!.kb_id).toBe("kb1");
    expect(received!.filename).toBe("员工手册 v3.pdf");
    expect(received!.impact).toContain("回收站");
    expect(received!.can_adopt).toBe(true);
    expect(received!.run_id).toBe("r1");
  });

  it("does not call onProposalPreview when handler is not provided", () => {
    const payload = makeProposal();
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
    };
    const block = `event: proposal_preview\ndata: ${JSON.stringify(payload)}`;
    expect(() => dispatchChatSseBlock(block, handlers)).not.toThrow();
  });

  it("drops proposal_preview event with missing required fields", () => {
    let called = false;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onProposalPreview: () => {
        called = true;
      },
    };
    const block = `event: proposal_preview\ndata: ${JSON.stringify({ operation: "delete" })}`;
    dispatchChatSseBlock(block, handlers);
    expect(called).toBe(false);
  });
});

describe("G5 submitDocumentWrite", () => {
  const input = {
    thread_id: "t1",
    kb_id: "kb1",
    document_id: "d1",
    operation: "delete" as const,
    run_id: "r1",
  };

  it("posts to the submit endpoint and returns approval_id", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(
          JSON.stringify({ approval_id: "ap1", status: "pending" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );
    const getToken = await import("@/lib/auth-storage");
    vi.spyOn(getToken, "getAccessToken").mockReturnValue("tok");

    const result = await submitDocumentWrite(input);
    expect(result.approval_id).toBe("ap1");
    expect(result.status).toBe("pending");

    vi.unstubAllGlobals();
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ detail: "没有权限执行此操作" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const getToken = await import("@/lib/auth-storage");
    vi.spyOn(getToken, "getAccessToken").mockReturnValue("tok");

    await expect(submitDocumentWrite(input)).rejects.toThrow(
      "没有权限执行此操作",
    );

    vi.unstubAllGlobals();
  });
});

describe("G5 dispatchChatSseBlock — clarify", () => {
  function makeClarify(
    overrides: Partial<ClarifyPayload> = {},
  ): ClarifyPayload {
    return {
      operation: "delete",
      run_id: "r1",
      options: [
        { document_id: "d1", filename: "年假制度 v1.docx", kb_id: "kb1" },
        { document_id: "d2", filename: "年假制度 v2.docx", kb_id: "kb1" },
      ],
      ...overrides,
    };
  }

  it("calls onClarify with options", () => {
    const payload = makeClarify();
    let received: ClarifyPayload | undefined;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onClarify: (p) => {
        received = p;
      },
    };
    const block = `event: clarify\ndata: ${JSON.stringify(payload)}`;
    dispatchChatSseBlock(block, handlers);
    expect(received).toBeDefined();
    expect(received!.operation).toBe("delete");
    expect(received!.options).toHaveLength(2);
    expect(received!.options[0].document_id).toBe("d1");
  });

  it("drops clarify event with missing options", () => {
    let called = false;
    const handlers: ChatStreamHandlers = {
      onCitation: () => {},
      onToken: () => {},
      onDone: () => {},
      onClarify: () => {
        called = true;
      },
    };
    const block = `event: clarify\ndata: ${JSON.stringify({ operation: "delete" })}`;
    dispatchChatSseBlock(block, handlers);
    expect(called).toBe(false);
  });
});

describe("G5 clarifyDocumentWrite", () => {
  it("posts to clarify endpoint and returns proposal payload", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(
          JSON.stringify({
            operation: "delete",
            document_id: "d1",
            kb_id: "kb1",
            filename: "年假制度 v1.docx",
            kb_name: "HR 库",
            impact: "将移入回收站",
            conflict: null,
            run_id: "r9",
            can_adopt: true,
            double_confirm: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    );
    const getToken = await import("@/lib/auth-storage");
    vi.spyOn(getToken, "getAccessToken").mockReturnValue("tok");

    const result = await clarifyDocumentWrite({
      thread_id: "t1",
      document_id: "d1",
      operation: "delete",
    });
    expect(result.document_id).toBe("d1");
    expect(result.run_id).toBe("r9");
    expect(result.double_confirm).toBe(true);

    vi.unstubAllGlobals();
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ detail: "文档不存在" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const getToken = await import("@/lib/auth-storage");
    vi.spyOn(getToken, "getAccessToken").mockReturnValue("tok");

    await expect(
      clarifyDocumentWrite({
        thread_id: "t1",
        document_id: "d1",
        operation: "delete",
      }),
    ).rejects.toThrow("文档不存在");

    vi.unstubAllGlobals();
  });
});
