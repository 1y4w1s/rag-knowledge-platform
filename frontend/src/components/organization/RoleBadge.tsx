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

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.7rem] font-medium",
        isOwner
          ? "bg-[var(--role-bg)] text-[var(--role-ink)] ring-1 ring-[color:var(--role)]/35"
          : "bg-[var(--role-bg)] text-[var(--role-ink)]",
        className,
      )}
    >
      {label}
    </span>
  );
}
