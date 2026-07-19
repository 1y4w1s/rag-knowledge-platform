import type { OrgUnit } from "@/lib/org-units-api";

export interface DepartmentTreeNode {
  unit: OrgUnit;
  children: DepartmentTreeNode[];
}

export function buildDepartmentTree(units: OrgUnit[]): {
  root: DepartmentTreeNode | null;
  byId: Map<string, DepartmentTreeNode>;
} {
  const safeUnits = Array.isArray(units) ? units : [];
  const byId = new Map<string, DepartmentTreeNode>();
  for (const unit of safeUnits) {
    byId.set(unit.id, { unit, children: [] });
  }

  let root: DepartmentTreeNode | null = null;
  for (const unit of safeUnits) {
    const node = byId.get(unit.id);
    if (!node) continue;
    if (unit.parent_id === null) {
      root = node;
      continue;
    }
    const parent = byId.get(unit.parent_id);
    if (parent) parent.children.push(node);
  }

  const sortChildren = (node: DepartmentTreeNode) => {
    node.children.sort((a, b) =>
      a.unit.name.localeCompare(b.unit.name, "zh-CN"),
    );
    node.children.forEach(sortChildren);
  };
  if (root) sortChildren(root);

  return { root, byId };
}
