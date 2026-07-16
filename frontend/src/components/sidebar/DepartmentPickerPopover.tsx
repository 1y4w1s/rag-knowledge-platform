import { useEffect, useRef, useState, type RefObject } from "react";

import type { DepartmentPickerModel } from "@/lib/department-picker-tree";
import { DEPARTMENT_ALL, type DepartmentScopeId } from "@/lib/department-storage";
import type { DepartmentTreeNode } from "@/lib/org-unit-tree";
import { cn } from "@/lib/utils";

interface DepartmentPickerPopoverProps {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  orgName: string;
  model: DepartmentPickerModel;
  selectedId: string | null;
  onSelect: (next: DepartmentScopeId) => void;
  onClose: () => void;
}

function PickerTreeNode({
  node,
  orgName,
  selectedId,
  selectableIds,
  onSelect,
  depth,
  collapsedIds,
  onToggle,
}: {
  node: DepartmentTreeNode;
  orgName: string;
  selectedId: string | null;
  selectableIds: Set<string>;
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
  const selectable = selectableIds.has(node.unit.id);

  return (
    <li>
      <div
        className="flex items-center gap-1"
        style={{ paddingLeft: depth * 12 }}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={collapsed ? "展开" : "折叠"}
            className="dept-picker-tree-toggle"
            onClick={() => onToggle(node.unit.id)}
          >
            {collapsed ? "▸" : "▾"}
          </button>
        ) : (
          <span className="dept-picker-tree-spacer" aria-hidden />
        )}
        <button
          type="button"
          disabled={!selectable}
          className={cn(
            "dept-picker-tree-node",
            selected && "selected",
            !selectable && "disabled",
          )}
          onClick={() => {
            if (!selectable) return;
            onSelect(node.unit.id);
          }}
        >
          <span className="dept-picker-tree-label">{label}</span>
        </button>
      </div>
      {hasChildren && !collapsed ? (
        <ul className="dept-picker-tree-children">
          {node.children.map((child) => (
            <PickerTreeNode
              key={child.unit.id}
              node={child}
              orgName={orgName}
              selectedId={selectedId}
              selectableIds={selectableIds}
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

export function DepartmentPickerPopover({
  open,
  anchorRef,
  orgName,
  model,
  selectedId,
  onSelect,
  onClose,
}: DepartmentPickerPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!open || !popoverRef.current || !anchorRef.current) return;
    const anchor = anchorRef.current;
    popoverRef.current.style.top = `${anchor.offsetTop + anchor.offsetHeight + 8}px`;
    popoverRef.current.style.left = `${anchor.offsetLeft + anchor.offsetWidth + 8}px`;
  }, [open, anchorRef, orgName, model.root?.unit.id]);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (popoverRef.current?.contains(target)) return;
      if (anchorRef.current?.contains(target)) return;
      onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, onClose, anchorRef]);

  useEffect(() => {
    if (!open || !popoverRef.current) return;
    const first = popoverRef.current.querySelector<HTMLButtonElement>(
      ".dept-picker-tree-node:not(:disabled), .dept-picker-all-option",
    );
    first?.focus();
  }, [open]);

  function toggleCollapse(unitId: string) {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(unitId)) next.delete(unitId);
      else next.add(unitId);
      return next;
    });
  }

  if (!open) return null;

  return (
    <div
      ref={popoverRef}
      className="dept-picker-popover popover-base"
      role="dialog"
      aria-label="选择当前部门"
      aria-modal="true"
    >
      {model.showAllScopeOption ? (
        <button
          type="button"
          className={cn(
            "dept-picker-all-option",
            selectedId === DEPARTMENT_ALL && "selected",
          )}
          onClick={() => onSelect(DEPARTMENT_ALL)}
        >
          全公司
        </button>
      ) : null}

      {model.root ? (
        <ul className="dept-picker-tree">
          <PickerTreeNode
            node={model.root}
            orgName={orgName}
            selectedId={selectedId}
            selectableIds={model.selectableIds}
            onSelect={onSelect}
            depth={0}
            collapsedIds={collapsedIds}
            onToggle={toggleCollapse}
          />
        </ul>
      ) : (
        <p className="dept-picker-empty">暂无可用部门</p>
      )}
    </div>
  );
}
