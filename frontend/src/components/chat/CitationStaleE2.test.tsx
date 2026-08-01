import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { CitationChip } from "@/components/chat/CitationChip";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import {
  CITATION_RESOLVE_FAILED_LABEL,
  CITATION_STALE_NOTICE_DELETED,
  SOURCE_DELETED_CHIP_LABEL,
  SOURCE_DELETED_LABEL,
  type Citation,
} from "@/lib/chat-api";

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
});

describe("E2 CitationChip", () => {
  it("shows visible deleted status label", () => {
    render(
      <CitationChip
        index={1}
        citation={makeCitation({ source_status: "document_deleted" })}
        onClick={() => {}}
      />,
    );
    expect(screen.getByTestId("citation-chip-status").textContent).toBe(
      SOURCE_DELETED_CHIP_LABEL,
    );
    expect(screen.getByTestId("citation-chip").getAttribute("title")).toBe(
      SOURCE_DELETED_LABEL,
    );
  });

  it("disables expand for source_inaccessible", () => {
    render(
      <CitationChip
        index={1}
        citation={makeCitation({ source_status: "source_inaccessible" })}
        onClick={() => {}}
      />,
    );
    expect(screen.getByTestId("citation-chip")).toHaveProperty("disabled", true);
  });
});

describe("E2 ChatMessageList stale notice", () => {
  it("renders message-level notice when citation is document_deleted", () => {
    render(
      <MemoryRouter>
        <ChatMessageList
          kbId="kb-1"
          onToggleCitation={() => {}}
          messages={[
            {
              role: "assistant",
              content: "年假 10 天。",
              citations: [
                makeCitation({ source_status: "document_deleted" }),
              ],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("citation-stale-notice").textContent).toBe(
      CITATION_STALE_NOTICE_DELETED,
    );
  });

  it("does not render notice for available citations", () => {
    render(
      <MemoryRouter>
        <ChatMessageList
          kbId="kb-1"
          onToggleCitation={() => {}}
          messages={[
            {
              role: "assistant",
              content: "年假 10 天。",
              citations: [makeCitation({ source_status: "available" })],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("citation-stale-notice")).toBeNull();
  });
});

describe("E2 CitationPreview resolve failure", () => {
  it("does not mislabel resolve failure as document_deleted", async () => {
    resolveCitationMock.mockRejectedValueOnce(new Error("network"));
    render(
      <MemoryRouter>
        <CitationPreview
          kbId="kb-1"
          citation={makeCitation({ source_status: "available" })}
        />
      </MemoryRouter>,
    );
    const banner = await screen.findByTestId("citation-preview-banner");
    expect(banner.textContent).toBe(CITATION_RESOLVE_FAILED_LABEL);
    expect(banner.textContent).not.toBe(SOURCE_DELETED_LABEL);
  });

  it("shows deleted banner from enriched source_status without resolve", () => {
    render(
      <MemoryRouter>
        <CitationPreview
          kbId="kb-1"
          citation={makeCitation({ source_status: "document_deleted" })}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("citation-preview-banner").textContent).toBe(
      SOURCE_DELETED_LABEL,
    );
    expect(resolveCitationMock).not.toHaveBeenCalled();
  });
});

describe("E2 CitationChip click still works for deleted", () => {
  it("allows expand click when document_deleted", () => {
    const onClick = vi.fn();
    render(
      <CitationChip
        index={1}
        citation={makeCitation({ source_status: "document_deleted" })}
        onClick={onClick}
      />,
    );
    fireEvent.click(screen.getByTestId("citation-chip"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
