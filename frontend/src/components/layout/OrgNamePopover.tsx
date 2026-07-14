import { useEffect, useRef, type RefObject } from "react";
import { Link } from "react-router-dom";

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
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open || !popoverRef.current || !anchorRef.current) return;
    const seg = anchorRef.current;
    popoverRef.current.style.top = `${seg.offsetTop + seg.offsetHeight + 8}px`;
  }, [open, anchorRef, fullName]);

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
      ".org-popover-actions button:not(.hidden)",
    );
    first?.focus();
  }, [open]);

  if (!open) return null;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(fullName);
    } catch {
      onCopyError("请手动选择复制");
    }
  }

  const shortLabel = formatOrgLabel(fullName);

  return (
    <div
      ref={popoverRef}
      className="org-popover"
      role="dialog"
      aria-label="团队全称"
      aria-modal="true"
    >
      <div className="org-popover-title">团队全称（存库展示名）</div>
      <div className="org-popover-body">{fullName}</div>
      <div className="org-popover-meta">
        侧栏短标签：「{shortLabel}」· 策略 C3a/C3b
      </div>
      <div className="org-popover-actions">
        <button type="button" onClick={() => void handleCopy()}>
          复制
        </button>
        {isAdmin ? (
          <Link
            to="/organization/settings"
            className="org-popover-link"
            onClick={onClose}
          >
            组织设置
          </Link>
        ) : null}
        <button type="button" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>
  );
}
