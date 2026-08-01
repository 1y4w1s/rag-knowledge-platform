import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { ClarifyCard } from "@/components/chat/ClarifyCard";
import type { ClarifyPayload } from "@/lib/chat-api";

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

describe("G5 ClarifyCard", () => {
  it("renders all candidate options", () => {
    render(<ClarifyCard clarify={makeClarify()} />);
    expect(screen.getByTestId("clarify-option-d1")).toBeDefined();
    expect(screen.getByTestId("clarify-option-d2")).toBeDefined();
    expect(screen.getByText("年假制度 v1.docx")).toBeDefined();
    expect(screen.getByText("年假制度 v2.docx")).toBeDefined();
  });

  it("calls onSelect with document id and operation", () => {
    const onSelect = vi.fn();
    render(<ClarifyCard clarify={makeClarify()} onSelect={onSelect} />);

    fireEvent.click(screen.getByTestId("clarify-option-d2"));
    expect(onSelect).toHaveBeenCalledWith("d2", "delete");
  });

  it("disables options while clarifying", () => {
    const onSelect = vi.fn();
    render(
      <ClarifyCard clarify={makeClarify()} onSelect={onSelect} clarifying={true} />,
    );
    const btn = screen.getByTestId("clarify-option-d1") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(screen.getByText("正在生成操作提案…")).toBeDefined();
  });

  it("renders error message when present", () => {
    render(<ClarifyCard clarify={makeClarify()} error="澄清失败，请重试" />);
    expect(screen.getByText("澄清失败，请重试")).toBeDefined();
  });

  it("uses restore verb label for restore operation", () => {
    render(<ClarifyCard clarify={makeClarify({ operation: "restore" })} />);
    expect(screen.getByText(/请选择要恢复/)).toBeDefined();
  });
});
