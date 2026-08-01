import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { DocumentStatusBadge } from "./DocumentStatusBadge";

describe("DocumentStatusBadge", () => {
  test("queued shows queue copy distinct from processing", () => {
    render(<DocumentStatusBadge status="queued" />);
    expect(screen.getByText("排队等待处理")).toBeDefined();
  });

  test("processing with stage shows stage label", () => {
    render(
      <DocumentStatusBadge status="processing" processingStage="chunking" />,
    );
    expect(screen.getByText("正在切片…")).toBeDefined();
  });

  test("processing with OCR detail shows recognizing label", () => {
    render(
      <DocumentStatusBadge
        status="processing"
        processingStage="parsing"
        progressDetail="第 2/8 页"
      />,
    );
    expect(screen.getByText("正在识别…")).toBeDefined();
  });

  test.each([
    { status: "completed" as const, text: "完成", cls: "doc-badge-ok" },
    { status: "failed" as const, text: "失败", cls: "doc-badge-err" },
  ])("renders $text badge for $status", ({ status, text, cls }) => {
    render(<DocumentStatusBadge status={status} />);
    const badge = screen.getByText(text);
    expect(badge).toBeDefined();
    expect(badge.className).toContain(cls);
  });
});
