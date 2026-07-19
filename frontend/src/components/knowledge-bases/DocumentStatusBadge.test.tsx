import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { DocumentStatusBadge } from "./DocumentStatusBadge";

describe("DocumentStatusBadge", () => {
  test.each([
    { status: "completed" as const, text: "完成", cls: "doc-badge-ok" },
    { status: "queued" as const, text: "处理中", cls: "doc-badge-wait" },
    { status: "processing" as const, text: "处理中", cls: "doc-badge-wait" },
    { status: "failed" as const, text: "失败", cls: "doc-badge-err" },
  ])("renders $text badge for $status", ({ status, text, cls }) => {
    render(<DocumentStatusBadge status={status} />);
    const badge = screen.getByText(text);
    expect(badge).toBeDefined();
    expect(badge.className).toContain(cls);
  });
});
