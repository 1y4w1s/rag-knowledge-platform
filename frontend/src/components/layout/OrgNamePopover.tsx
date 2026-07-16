import { createPortal } from "react-dom";
import { useEffect, type RefObject } from "react";
import { Link } from "react-router-dom";

import { useFloatingMenu } from "@/lib/use-floating-menu";
import { formatOrgLabel } from "@/lib/format-org-label";

interface OrgNamePopoverProps {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  fullName: string;
  isAdmin: boolean;
  onClose: () => void;
  onCopyError: (message: string) => void;
}

export function OrgNamePopover({
  open,
  anchorRef,
  fullName,
  isAdmin,
  onClose,
  onCopyError,
}: OrgNamePopoverProps) {
  const { floatingRef, style } = useFloatingMenu(
    anchorRef as React.RefObject<HTMLElement | null>,
    open,
  );

  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (floatingRef.current?.contains(target)) return;
      if (anchorRef.current?.contains(target)) return;
      onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, onClose, anchorRef, floatingRef]);

  useEffect(() => {
    if (!open || !floatingRef.current) return;
    const first = floatingRef.current.querySelector<HTMLButtonElement>(
      ".org-popover-actions button:not(.hidden)",
    );
    first?.focus();
  }, [open, floatingRef]);

  if (!open) return null;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(fullName);
    } catch {
      onCopyError("请手动选择复制");
    }
  }

  const shortLabel = formatOrgLabel(fullName);

  return createPortal(
    <div
      ref={floatingRef}
      style={style}
      className="popover-base z-[9999] w-[280px] px-[14px] py-[12px]"
      role="dialog"
      aria-label="团队全称"
      aria-modal="true"
    >
      <div className="mb-2 text-[0.72rem] font-semibold text-[var(--mut)]">团队全称（存库展示名）</div>
      <div className="max-h-[120px] overflow-y-auto break-all leading-[1.55] text-[var(--text)]">{fullName}</div>
      <div className="mt-2 text-[0.68rem] text-[var(--mut)]">
        侧栏短标签：「{shortLabel}」· 策略 C3a/C3b
      </div>
      <div className="mt-3 flex gap-2">
        <button type="button" className="rounded-md px-3 py-1.5 text-[0.75rem] font-medium text-[var(--action)] hover:bg-nav-on" onClick={() => void handleCopy()}>
          复制
        </button>
        {isAdmin ? (
          <Link
            to="/organization/settings"
            className="rounded-md px-3 py-1.5 text-[0.75rem] font-medium text-[var(--action)] hover:bg-nav-on"
            onClick={onClose}
          >
            组织设置
          </Link>
        ) : null}
        <button type="button" className="rounded-md px-3 py-1.5 text-[0.75rem] text-[var(--mut)] hover:bg-nav-on" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>,
    document.body,
  );
}
