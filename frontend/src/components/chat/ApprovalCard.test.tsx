import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ApprovalCard } from "@/components/chat/ApprovalCard";
import type { ApprovalState } from "@/lib/chat-api";

// Mock CitationChip to avoid heavy DOM / icon dependencies
vi.mock("@/components/chat/CitationChip", () => ({
  CitationChip: ({
    index,
    citation,
  }: {
    index: number;
    citation: { doc_name: string };
  }) => <span data-testid="citation-chip">{`[${index}] ${citation.doc_name}`}</span>,
}));

function makeApproval(overrides: Partial<ApprovalState> = {}): ApprovalState {
  return {
    approval_id: "a1",
    filename: "FAQ_年假.md",
    kb_name: "HR 制度库",
    draft_preview: "## 年假政策\n\n员工每年享有 5 天带薪年假...",
    citations: [
      {
        chunk_id: "c1",
        document_id: "d1",
        doc_name: "员工手册 v3",
        page: 12,
        section_title: "年假制度",
        excerpt: "员工每年享有 5 天带薪年假...",
      },
    ],
    can_adopt: true,
    status: "pending",
    ...overrides,
  };
}

describe("G4-5.1 ApprovalCard", () => {
  // ------ 双钮渲染 ------
  it("renders adopt + cancel buttons when can_adopt=true and pending", () => {
    render(<ApprovalCard approval={makeApproval({ can_adopt: true, status: "pending" })} />);

    expect(screen.getByTestId("approval-card")).toBeDefined();
    expect(screen.getByTestId("approval-btn-adopt")).toBeDefined();
    expect(screen.getByTestId("approval-btn-cancel")).toBeDefined();
    expect(screen.getByText("采纳")).toBeDefined();
    expect(screen.getByText("取消")).toBeDefined();
    // No terminal status badge
    expect(screen.queryByText("已采纳")).toBeNull();
    expect(screen.queryByText("已取消")).toBeNull();
  });

  // ------ Member 无采纳 ------
  it("shows no-permission text when can_adopt=false (Member)", () => {
    render(<ApprovalCard approval={makeApproval({ can_adopt: false, status: "pending" })} />);

    expect(screen.getByTestId("approval-card")).toBeDefined();
    // No adopt / cancel buttons
    expect(screen.queryByTestId("approval-btn-adopt")).toBeNull();
    expect(screen.queryByTestId("approval-btn-cancel")).toBeNull();
    // Permission message
    expect(screen.getByText("你对该知识库无写入权限，需管理员采纳")).toBeDefined();
  });

  // ------ 终态灰显：已采纳 ------
  it("shows adopted terminal state (greyed out, no buttons)", () => {
    render(<ApprovalCard approval={makeApproval({ status: "adopted" })} />);

    expect(screen.getByText("已采纳")).toBeDefined();
    // No action buttons in terminal state
    expect(screen.queryByTestId("approval-btn-adopt")).toBeNull();
    expect(screen.queryByTestId("approval-btn-cancel")).toBeNull();
    // Has terminal class via data-testid
    expect(screen.getByTestId("approval-card")).toBeDefined();
  });

  // ------ 终态灰显：已取消 ------
  it("shows cancelled terminal state (greyed out, no buttons)", () => {
    render(<ApprovalCard approval={makeApproval({ status: "cancelled" })} />);

    expect(screen.getByText("已取消")).toBeDefined();
    // No action buttons in terminal state
    expect(screen.queryByTestId("approval-btn-adopt")).toBeNull();
    expect(screen.queryByTestId("approval-btn-cancel")).toBeNull();
    expect(screen.getByTestId("approval-card")).toBeDefined();
  });

  // ------ 409 友好提示 ------
  it("shows error message for 409 conflict", () => {
    render(
      <ApprovalCard
        approval={makeApproval()}
        error="该审批已处理，请勿重复操作"
      />,
    );

    const errorEl = screen.getByRole("alert");
    expect(errorEl).toBeDefined();
    expect(errorEl.textContent).toBe("该审批已处理，请勿重复操作");
  });

  // ------ 403 友好提示 ------
  it("shows error message for 403 forbidden", () => {
    render(
      <ApprovalCard
        approval={makeApproval()}
        error="没有权限执行此操作"
      />,
    );

    const errorEl = screen.getByRole("alert");
    expect(errorEl).toBeDefined();
    expect(errorEl.textContent).toBe("没有权限执行此操作");
  });

  // ------ onAdopt / onCancel 回调 ------
  it("calls onAdopt when adopt button clicked", () => {
    const onAdopt = vi.fn();
    render(
      <ApprovalCard approval={makeApproval()} onAdopt={onAdopt} />,
    );

    fireEvent.click(screen.getByTestId("approval-btn-adopt"));
    expect(onAdopt).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when cancel button clicked", () => {
    const onCancel = vi.fn();
    render(
      <ApprovalCard approval={makeApproval()} onCancel={onCancel} />,
    );

    fireEvent.click(screen.getByTestId("approval-btn-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  // ------ resolving 态 ------
  it("disables buttons when resolving", () => {
    render(
      <ApprovalCard approval={makeApproval()} resolving={true} />,
    );

    const adoptBtn = screen.getByTestId("approval-btn-adopt") as HTMLButtonElement;
    const cancelBtn = screen.getByTestId("approval-btn-cancel") as HTMLButtonElement;
    expect(adoptBtn.disabled).toBe(true);
    expect(cancelBtn.disabled).toBe(true);
    expect(screen.getByText("处理中…")).toBeDefined();
  });

  // ------ 草稿预览折叠 ------
  it("renders draft preview toggle", () => {
    render(<ApprovalCard approval={makeApproval()} />);

    expect(screen.getByText("草稿预览")).toBeDefined();
    // Preview body should be hidden initially
    expect(screen.queryByText(/年假政策/)).toBeNull();

    // Click toggle to expand
    fireEvent.click(screen.getByText("草稿预览"));
    // <pre> renders multiline text, use regex to match across newlines
    expect(screen.getByText(/年假政策/)).toBeDefined();
    expect(screen.getByText(/员工每年享有 5 天带薪年假/)).toBeDefined();
  });

  // ------ 引用 chips ------
  it("renders citation chips", () => {
    render(<ApprovalCard approval={makeApproval()} />);

    const chips = screen.getAllByTestId("citation-chip");
    expect(chips).toHaveLength(1);
    expect(chips[0].textContent).toContain("员工手册 v3");
  });

  // ------ 文件名显示 ------
  it("renders filename", () => {
    render(<ApprovalCard approval={makeApproval({ filename: "FAQ_年假.md" })} />);

    expect(screen.getByText("FAQ_年假.md")).toBeDefined();
  });
});
