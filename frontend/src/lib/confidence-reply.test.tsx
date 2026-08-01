import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ChatMessageList } from "@/components/chat/ChatMessageList";
import {
  PARTIAL_ANSWER_NOTICE,
  PARTIAL_DISCLAIMER_ZH,
  hasPartialAnswerDisclaimer,
} from "@/lib/confidence-reply";

vi.mock("@/lib/workspace-context", () => ({
  useWorkspace: () => ({
    workspace: "personal",
    isTeamWorkspace: false,
  }),
}));

vi.mock("@/lib/department-context", () => ({
  useDepartment: () => ({ departmentId: null }),
}));

describe("E3 confidence-reply", () => {
  it("detects ZH disclaimer prefix", () => {
    expect(
      hasPartialAnswerDisclaimer(
        `${PARTIAL_DISCLAIMER_ZH}\n\n正式员工年假 10 天。`,
      ),
    ).toBe(true);
    expect(hasPartialAnswerDisclaimer("正式员工年假 10 天。")).toBe(false);
  });

  it("shows muted notice under assistant message with citations", () => {
    render(
      <MemoryRouter>
        <ChatMessageList
          kbId="kb1"
          citationMode="kb"
          onToggleCitation={() => undefined}
          messages={[
            {
              role: "assistant",
              content: `${PARTIAL_DISCLAIMER_ZH}\n\n年假 10 天。`,
              citations: [
                {
                  chunk_id: "c1",
                  document_id: "d1",
                  doc_name: "手册.md",
                  page: null,
                  section_title: null,
                  excerpt: "年假 10 天",
                },
              ],
              expandedIndex: null,
              createdAt: "2026-07-21T00:00:00Z",
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("partial-answer-notice").textContent).toBe(
      PARTIAL_ANSWER_NOTICE,
    );
  });
});
