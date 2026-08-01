import { useLayoutEffect, useRef, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";
import { GUARD_TOAST } from "@/lib/guard-toast";
import { canManageOwnUnitMembers } from "@/lib/org-permissions";
import { useWorkspace } from "@/lib/workspace-context";

/** NW-24 U1：仅非公司 Admin 的 unit_admin 可进「我的部门成员」。 */
export function UnitAdminMembersGuard({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { redirectWithGuardToast } = useWorkspace();
  const blocked = !canManageOwnUnitMembers(user);
  const handledRef = useRef(false);

  useLayoutEffect(() => {
    if (!blocked) {
      handledRef.current = false;
      return;
    }
    if (handledRef.current) return;
    handledRef.current = true;
    redirectWithGuardToast(GUARD_TOAST.T1);
  }, [blocked, redirectWithGuardToast]);

  if (blocked) return null;

  return children;
}
