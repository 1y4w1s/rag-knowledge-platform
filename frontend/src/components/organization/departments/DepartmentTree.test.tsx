import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DepartmentTree } from "./DepartmentTree";
import type { DepartmentTreeNode } from "@/lib/org-unit-tree";

function makeNode(
  id: string,
  name: string,
  parentId: string | null,
  childCount = 0,
): DepartmentTreeNode {
  return {
    unit: {
      id,
      org_id: "org-1",
      parent_id: parentId,
      name,
      depth: parentId === null ? 0 : 1,
      child_count: childCount,
      member_count: 0,
      kb_count: 0,
      created_at: "2026-01-01T00:00:00Z",
    },
    children: [],
  };
}

describe("DepartmentTree", () => {
  it("renders root label and child nodes", () => {
    const root: DepartmentTreeNode = {
      ...makeNode("root", "知岸演示", null, 2),
      children: [makeNode("c1", "研发部", "root"), makeNode("c2", "产品部", "root")],
    };
    render(
      <DepartmentTree
        root={root}
        orgName="知岸演示公司"
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("知岸演示公司")).toBeDefined();
    expect(screen.getByText("研发部")).toBeDefined();
    expect(screen.getByText("产品部")).toBeDefined();
  });

  it("uses SVG chevron and no geometric arrow characters", () => {
    const root: DepartmentTreeNode = {
      ...makeNode("root", "知岸演示", null, 1),
      children: [makeNode("c1", "研发部", "root")],
    };
    render(
      <DepartmentTree
        root={root}
        orgName="知岸演示公司"
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(document.body.textContent).not.toMatch(/[▸▾]/);
    const toggle = screen.getByRole("button", { name: "折叠" });
    expect(toggle.querySelector("svg")).toBeDefined();
  });

  it("toggles children with the chevron button", async () => {
    const root: DepartmentTreeNode = {
      ...makeNode("root", "知岸演示", null, 1),
      children: [makeNode("c1", "研发部", "root")],
    };
    render(
      <DepartmentTree
        root={root}
        orgName="知岸演示公司"
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    const toggle = screen.getByRole("button", { name: "折叠" });
    fireEvent.click(toggle);
    expect(screen.queryByText("研发部")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "展开" }));
    expect(screen.getByText("研发部")).toBeDefined();
  });

  it("uses warm-neutral count badge, not cold blue", () => {
    const root = makeNode("root", "知岸演示", null, 3);
    render(
      <DepartmentTree
        root={root}
        orgName="知岸演示公司"
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    const badge = screen.getByText("3");
    expect(badge.className).toContain("bg-[#F2EDE7]");
    expect(badge.className).not.toContain("rgba(30,58,95");
  });

  it("calls onSelect when a node is clicked", async () => {
    const root: DepartmentTreeNode = {
      ...makeNode("root", "知岸演示", null, 1),
      children: [makeNode("c1", "研发部", "root")],
    };
    const onSelect = vi.fn();
    render(
      <DepartmentTree
        root={root}
        orgName="知岸演示公司"
        selectedId={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("研发部"));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });
});
