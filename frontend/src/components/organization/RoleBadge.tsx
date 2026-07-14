import type { OrgRole } from "@/lib/auth-storage";

import { cn } from "@/lib/utils";
import { formatOrgRoleLabel } from "@/lib/organization-api";

export function RoleBadge({
  role,
  isOwner = false,
  className,
}: {
  role: OrgRole;
  isOwner?: boolean;
  className?: string;
}) {
  const label = formatOrgRoleLabel(role, isOwner);
  const tone = isOwner
    ? "bg-[var(--action)] text-white shadow-sm"
    : role === "admin"
      ? "bg-[var(--nav-active-bg)] text-[var(--nav-active-text)]"
      : "bg-[var(--ubg)] text-[var(--mut-warm)]";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.7rem] font-medium",
        tone,
        className,
      )}
    >
      {label}
    </span>
  );
}
