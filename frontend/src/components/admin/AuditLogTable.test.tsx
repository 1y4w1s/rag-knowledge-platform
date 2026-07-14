import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuditLogTable } from "./AuditLogTable";
import type { AuditLog } from "@/lib/audit-api";

function makeRow(action: string): AuditLog {
  return {
    id: `log-${action}`,
    action,
    actor_user_id: "a1b2c3d4-0001-4aa1-8f00-0000000000aa",
    resource_type: null,
    resource_id: null,
    kb_id: "b1c2d3e4-0001-4aa1-8f00-000000000001",
    details: { filename: "test.pdf" },
    ip: "127.0.0.1",
    created_at: "2026-07-01T10:00:00",
  };
}

describe("AuditLogTable", () => {
  it("renders a neutral audit tag for normal actions (no amber)", () => {
    render(<AuditLogTable items={[makeRow("document.upload")]} />);
    const tag = screen.getByText("上传文档");
    expect(tag.className).toContain("audit-tag");
    expect(tag.className).not.toContain("err");
    expect(tag.className).not.toContain("doc-badge-wait");
  });

  it("renders a red err tag for failed login", () => {
    render(<AuditLogTable items={[makeRow("auth.login_failed")]} />);
    const tag = screen.getByText("登录失败");
    expect(tag.className).toContain("audit-tag");
    expect(tag.className).toContain("err");
  });

  it("renders a red err tag for storage cleanup failure", () => {
    render(<AuditLogTable items={[makeRow("storage.cleanup_failed")]} />);
    const tag = screen.getByText("磁盘清理失败");
    expect(tag.className).toContain("err");
  });

  it("never uses the amber processing badge across mixed rows", () => {
    render(
      <AuditLogTable
        items={[
          makeRow("document.upload"),
          makeRow("auth.login_failed"),
          makeRow("kb.delete"),
          makeRow("storage.cleanup_failed"),
        ]}
      />,
    );
    expect(document.body.innerHTML).not.toContain("doc-badge-wait");
  });
});
