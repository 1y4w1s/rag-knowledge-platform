import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ProposalPreviewCard } from "@/components/chat/ProposalPreviewCard";
import type { ProposalState } from "@/lib/chat-api";

function makeProposal(
  overrides: Partial<ProposalState> = {},
): ProposalState {
  return {
    operation: "delete",
    document_id: "d1",
    kb_id: "kb1",
    filename: "员工手册 v3.pdf",
    kb_name: "HR 制度库",
    impact: "该文档将被移入回收站。",
    conflict: null,
    run_id: "r1",
    can_adopt: true,
    ...overrides,
  };
}

describe("G5 ProposalPreviewCard", () => {
  it("renders operation label, filename, kb_name and impact", () => {
    render(<ProposalPreviewCard proposal={makeProposal()} />);

    expect(screen.getByTestId("proposal-preview-card")).toBeDefined();
    expect(screen.getByText("删除文档")).toBeDefined();
    expect(screen.getByText("员工手册 v3.pdf")).toBeDefined();
    expect(screen.getByText("HR 制度库")).toBeDefined();
    expect(screen.getByText("该文档将被移入回收站。")).toBeDefined();
  });

  it("renders conflict warning when conflict present", () => {
    render(
      <ProposalPreviewCard
        proposal={makeProposal({ conflict: "该文档正在处理中，删除将失败。" })}
      />,
    );
    expect(
      screen.getByText("该文档正在处理中，删除将失败。"),
    ).toBeDefined();
  });

  it("hides submit button when can_adopt=false (Member)", () => {
    render(<ProposalPreviewCard proposal={makeProposal({ can_adopt: false })} />);

    expect(screen.queryByTestId("proposal-btn-submit")).toBeNull();
    expect(
      screen.getByText("你对该知识库无写入权限，无法提交审批，需管理员操作"),
    ).toBeDefined();
  });

  it("calls onSubmit when submit button clicked", () => {
    const onSubmit = vi.fn();
    render(<ProposalPreviewCard proposal={makeProposal()} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when cancel button clicked", () => {
    const onCancel = vi.fn();
    render(<ProposalPreviewCard proposal={makeProposal()} onCancel={onCancel} />);

    fireEvent.click(screen.getByTestId("proposal-btn-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders restore operation label", () => {
    render(<ProposalPreviewCard proposal={makeProposal({ operation: "restore" })} />);
    expect(screen.getByText("恢复文档")).toBeDefined();
  });

  it("disables buttons while submitting", () => {
    render(<ProposalPreviewCard proposal={makeProposal()} submitting={true} />);
    const submitBtn = screen.getByTestId(
      "proposal-btn-submit",
    ) as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);
    expect(screen.getByText("提交中…")).toBeDefined();
  });

  it("single click submits when double_confirm is false", () => {
    const onSubmit = vi.fn();
    render(
      <ProposalPreviewCard
        proposal={makeProposal({ double_confirm: false })}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("requires two clicks when double_confirm is true", () => {
    const onSubmit = vi.fn();
    render(
      <ProposalPreviewCard
        proposal={makeProposal({ double_confirm: true })}
        onSubmit={onSubmit}
      />,
    );
    // 第一次点击：仅武装（armed），不提交
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByTestId("proposal-btn-rethink")).toBeDefined();
    expect(screen.getByText("再次确认，提交审批")).toBeDefined();
    // 第二次点击：提交
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("disarms on 再想想 and requires re-arming before submit", () => {
    const onSubmit = vi.fn();
    render(
      <ProposalPreviewCard
        proposal={makeProposal({ double_confirm: true })}
        onSubmit={onSubmit}
      />,
    );
    // 第一次点击：武装
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByTestId("proposal-btn-rethink")).toBeDefined();
    // 再想想：解除武装，回到「确认」初态
    fireEvent.click(screen.getByTestId("proposal-btn-rethink"));
    expect(screen.queryByTestId("proposal-btn-rethink")).toBeNull();
    expect(screen.getByText("确认")).toBeDefined();
    // 重新点击：再次武装（不提交）
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByTestId("proposal-btn-rethink")).toBeDefined();
    // 再次确认：提交
    fireEvent.click(screen.getByTestId("proposal-btn-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
