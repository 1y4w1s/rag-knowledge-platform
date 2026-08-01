import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ChatMessageList } from "@/components/chat/ChatMessageList";
import type { Citation } from "@/lib/chat-api";

vi.mock("@/lib/workspace-context", () => ({
  useWorkspace: () => ({
    workspace: "personal",
    isTeamWorkspace: false,
  }),
}));

vi.mock("@/lib/department-context", () => ({
  useDepartment: () => ({ departmentId: null }),
}));

const resolveCitationMock = vi.fn();
vi.mock("@/lib/chat-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/chat-api")>(
    "@/lib/chat-api",
  );
  return {
    ...actual,
    resolveCitation: (...args: unknown[]) => resolveCitationMock(...args),
  };
});

import { CitationPreview } from "@/components/chat/CitationPreview";

function makeCitation(overrides: Partial<Citation> = {}): Citation {
  return {
    chunk_id: "c1",
    document_id: "d1",
    doc_name: "员工手册.md",
    page: 1,
    section_title: "年假",
    excerpt: "正式员工年假 10 天",
    ...overrides,
  };
}

beforeEach(() => {
  resolveCitationMock.mockReset();
  resolveCitationMock.mockResolvedValue({
    document_id: "d1",
    chunk_id: "c1",
    source_status: "available",
    doc_name: "员工手册.md",
  });
});

describe("F2 CitationPreview workspace title", () => {
  it("includes kb_name in preview title when scopeMode=workspace", async () => {
    render(
      <MemoryRouter>
        <CitationPreview
          kbId="kb-1"
          scopeMode="workspace"
          citation={makeCitation({
            kb_id: "kb-1",
            kb_name: "人事制度库",
            source_status: "available",
          })}
        />
      </MemoryRouter>,
    );
    const preview = await screen.findByTestId("citation-preview");
    expect(preview.textContent).toContain("人事制度库");
    expect(preview.textContent).toContain("员工手册.md");
  });
});

describe("F2 ChatMessageList kb boundary notice", () => {
  it("shows multi-kb summary in workspace mode", () => {
    render(
      <MemoryRouter>
        <ChatMessageList
          kbId=""
          citationMode="workspace"
          onToggleCitation={() => {}}
          messages={[
            {
              role: "assistant",
              content: "年假 10 天。",
              citations: [
                makeCitation({ kb_id: "a", kb_name: "人事库" }),
                makeCitation({
                  chunk_id: "c2",
                  kb_id: "b",
                  kb_name: "研发规范库",
                }),
              ],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("citation-kb-boundary").textContent).toBe(
      "本回答引用：人事库 · 研发规范库",
    );
  });

  it("hides summary for single kb or kb mode", () => {
    const { rerender } = render(
      <MemoryRouter>
        <ChatMessageList
          kbId=""
          citationMode="workspace"
          onToggleCitation={() => {}}
          messages={[
            {
              role: "assistant",
              content: "年假 10 天。",
              citations: [makeCitation({ kb_name: "人事库" })],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("citation-kb-boundary")).toBeNull();

    rerender(
      <MemoryRouter>
        <ChatMessageList
          kbId="kb-1"
          citationMode="kb"
          onToggleCitation={() => {}}
          messages={[
            {
              role: "assistant",
              content: "年假 10 天。",
              citations: [
                makeCitation({ kb_name: "人事库" }),
                makeCitation({ chunk_id: "c2", kb_name: "研发规范库" }),
              ],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("citation-kb-boundary")).toBeNull();
  });
});
