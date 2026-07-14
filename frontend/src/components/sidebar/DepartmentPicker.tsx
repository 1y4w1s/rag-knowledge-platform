import { useCallback, useEffect, useRef, useState } from "react";

import { Building2, ChevronDown } from "lucide-react";

import { DepartmentPickerPopover } from "@/components/sidebar/DepartmentPickerPopover";
import { useAuth } from "@/lib/auth-context";
import { resolveDepartmentShortLabel } from "@/lib/department-picker-tree";
import { useDepartment } from "@/lib/department-context";
import type { DepartmentScopeId } from "@/lib/department-storage";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";
import { useDepartmentPicker } from "@/lib/use-department-picker";
import { useWorkspace } from "@/lib/workspace-context";

export function DepartmentPicker() {
  const { user } = useAuth();
  const { isTeamWorkspace } = useWorkspace();
  const { departmentId, setDepartment } = useDepartment();
  const { model, unitsById, orgName, loading } = useDepartmentPicker();
  const { close: closeDrawer } = useMobileDrawer();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const focusReturnRef = useRef<HTMLElement | null>(null);

  const shortLabel = resolveDepartmentShortLabel({
    departmentId,
    unitsById,
    loading,
  });

  const closePopover = useCallback(() => {
    setOpen(false);
    if (
      focusReturnRef.current &&
      typeof focusReturnRef.current.focus === "function"
    ) {
      focusReturnRef.current.focus();
      focusReturnRef.current = null;
    }
    triggerRef.current?.setAttribute("aria-expanded", "false");
  }, []);

  const openPopover = useCallback(() => {
    focusReturnRef.current = document.activeElement as HTMLElement | null;
    setOpen(true);
    triggerRef.current?.setAttribute("aria-expanded", "true");
  }, []);

  const togglePopover = useCallback(() => {
    if (open) closePopover();
    else openPopover();
  }, [open, closePopover, openPopover]);

  const handleSelect = useCallback(
    (next: DepartmentScopeId) => {
      setDepartment(next);
      closePopover();
      closeDrawer();
    },
    [setDepartment, closePopover, closeDrawer],
  );

  useEffect(() => {
    if (!isTeamWorkspace) closePopover();
  }, [isTeamWorkspace, closePopover]);

  if (!isTeamWorkspace || !user?.org_id) return null;

  return (
    <div className="dept-picker-wrap" ref={wrapRef}>
      <button
        ref={triggerRef}
        type="button"
        className="dept-picker-trigger"
        aria-label={`当前部门：${shortLabel}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={togglePopover}
      >
        <span className="dept-picker-icon" aria-hidden>
          <Building2 className="h-4 w-4" />
        </span>
        <span className="dept-picker-value" title={shortLabel}>
          {shortLabel}
        </span>
        <span className="dept-picker-chevron" aria-hidden>
          <ChevronDown className="h-3.5 w-3.5" />
        </span>
      </button>
      <DepartmentPickerPopover
        open={open}
        anchorRef={wrapRef}
        orgName={orgName}
        model={model}
        selectedId={departmentId}
        onSelect={handleSelect}
        onClose={closePopover}
      />
    </div>
  );
}
