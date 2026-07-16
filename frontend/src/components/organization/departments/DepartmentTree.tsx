import { useState } from "react";
import { ChevronRight } from "lucide-react";

import type { DepartmentTreeNode } from "@/lib/org-unit-tree";
import { cn } from "@/lib/utils";

interface DepartmentTreeProps {
  root: DepartmentTreeNode | null;
  orgName: string;
  selectedId: string | null;
  onSelect: (unitId: string) => void;
}

function TreeNode({
  node,
  orgName,
  selectedId,
  onSelect,
  depth,
  collapsedIds,
  onToggle,
}: {
  node: DepartmentTreeNode;
  orgName: string;
  selectedId: string | null;
  onSelect: (unitId: string) => void;
  depth: number;
  collapsedIds: Set<string>;
  onToggle: (unitId: string) => void;
}) {
  const isRoot = node.unit.parent_id === null;
  const label = isRoot ? orgName : node.unit.name;
  const hasChildren = node.children.length > 0;
  const collapsed = collapsedIds.has(node.unit.id);
  const selected = selectedId === node.unit.id;

  return (
    <li>
      <div
        className="flex items-center gap-1"
        style={{ paddingLeft: depth * 18 }}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={collapsed ? "展开" : "折叠"}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted hover:bg-[color:color-mix(in_srgb,var(--ubg)_80%,transparent)] hover:text-foreground"
            onClick={() => onToggle(node.unit.id)}
          >
              <ChevronRight
                className={cn(
                  "h-4 w-4 transition-transform duration-150",
                  collapsed ? "" : "rotate-90",
                )}
              />
            </button>
        ) : (
          <span className="inline-block h-6 w-6 shrink-0" aria-hidden />
        )}
        <button
          type="button"
          className={cn(
            "relative flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors",
            selected
              ? "bg-[#EFEBE6] font-medium text-foreground before:absolute before:left-0 before:top-1/4 before:h-1/2 before:w-[3px] before:rounded-r-full before:bg-[var(--action)]"
              : "text-foreground hover:bg-[rgba(245,242,237,0.65)]",
          )}
          onClick={() => onSelect(node.unit.id)}
        >
          <span className="truncate">{label}</span>
          {node.unit.child_count > 0 ? (
            <span className="shrink-0 rounded-full bg-[#F2EDE7] px-1.5 py-0.5 text-[0.68rem] text-[var(--mut-warm)]">
              {node.unit.child_count}
            </span>
          ) : null}
        </button>
      </div>
      {hasChildren && !collapsed ? (
        <ul className="mt-0.5 space-y-0.5">
          {node.children.map((child) => (
            <TreeNode
              key={child.unit.id}
              node={child}
              orgName={orgName}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
              collapsedIds={collapsedIds}
              onToggle={onToggle}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function DepartmentTree({
  root,
  orgName,
  selectedId,
  onSelect,
}: DepartmentTreeProps) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set());

  function toggleCollapse(unitId: string) {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  }

  if (!root) {
    return (
      <p className="px-3 py-6 text-sm text-muted">暂无部门，请先新建一级部门。</p>
    );
  }

  return (
    <ul className="space-y-0.5">
      <TreeNode
        node={root}
        orgName={orgName}
        selectedId={selectedId}
        onSelect={onSelect}
        depth={0}
        collapsedIds={collapsedIds}
        onToggle={toggleCollapse}
      />
    </ul>
  );
}
