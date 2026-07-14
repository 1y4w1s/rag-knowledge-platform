import { useCallback, useRef, useState } from "react";

import { OrgNamePopover } from "@/components/layout/OrgNamePopover";
import { useAuth } from "@/lib/auth-context";
import { formatOrgLabel } from "@/lib/format-org-label";
import { useOrganizationName } from "@/lib/use-organization-name";
import { useWorkspace } from "@/lib/workspace-context";

export function WorkspaceSwitcher() {
  const { user } = useAuth();
  const { workspace, setWorkspace } = useWorkspace();
  const { name: orgFullName, loading: orgNameLoading } = useOrganizationName();
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [copyToast, setCopyToast] = useState<string | null>(null);
  const segRef = useRef<HTMLDivElement>(null);
  const chevronRef = useRef<HTMLButtonElement>(null);
  const focusReturnRef = useRef<HTMLElement | null>(null);

  const orgId = user?.org_id ?? null;
  const hasTeam = Boolean(orgId);
  const isPersonal = workspace === "personal";
  const isTeamActive = Boolean(orgId && workspace === orgId);
  const displayName = orgNameLoading ? "…" : orgFullName || "团队";
  const teamLabel = formatOrgLabel(displayName);

  const closePopover = useCallback(() => {
    setPopoverOpen(false);
    if (focusReturnRef.current && typeof focusReturnRef.current.focus === "function") {
      focusReturnRef.current.focus();
      focusReturnRef.current = null;
    }
    chevronRef.current?.setAttribute("aria-expanded", "false");
  }, []);

  const openPopover = useCallback(() => {
    if (!hasTeam) return;
    focusReturnRef.current = document.activeElement as HTMLElement | null;
    setPopoverOpen(true);
    chevronRef.current?.setAttribute("aria-expanded", "true");
  }, [hasTeam]);

  const togglePopover = useCallback(() => {
    if (popoverOpen) closePopover();
    else openPopover();
  }, [popoverOpen, closePopover, openPopover]);

  function switchToPersonal() {
    closePopover();
    if (workspace === "personal") return;
    setWorkspace("personal");
  }

  function switchToTeam() {
    if (!orgId) return;
    closePopover();
    if (workspace === orgId) return;
    setWorkspace(orgId);
  }

  function handleCopyError(message: string) {
    setCopyToast(message);
    window.setTimeout(() => setCopyToast(null), 4000);
  }

  if (!hasTeam) {
    return (
      <div className="ws-seg ws-seg-solo" ref={segRef}>
        <button
          type="button"
          className="on"
          data-ws="personal"
          onClick={switchToPersonal}
        >
          我的空间
        </button>
      </div>
    );
  }

  return (
    <>
      {copyToast ? (
        <div className="ws-copy-toast" role="status">
          {copyToast}
        </div>
      ) : null}
      <div className="ws-seg" ref={segRef}>
        <button
          type="button"
          className={isPersonal ? "on" : undefined}
          data-ws="personal"
          onClick={switchToPersonal}
        >
          我的空间
        </button>
        <div className={`ws-seg-team${isTeamActive ? " on" : ""}`}>
          <button
            type="button"
            className="ws-team-label"
            data-ws="team"
            title={displayName}
            onClick={switchToTeam}
          >
            {teamLabel}
          </button>
          <button
            ref={chevronRef}
            type="button"
            className="ws-fullname-btn"
            aria-label="查看团队全称"
            aria-expanded={popoverOpen}
            title="Popover 存库全称 · 不切换工作区"
            onClick={togglePopover}
          >
            ›
          </button>
        </div>
      </div>
      <OrgNamePopover
        open={popoverOpen}
        anchorRef={segRef}
        fullName={displayName}
        isAdmin={user?.org_role === "admin"}
        onClose={closePopover}
        onCopyError={handleCopyError}
      />
    </>
  );
}
