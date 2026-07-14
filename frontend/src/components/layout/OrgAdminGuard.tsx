import { useLayoutEffect, useRef, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";
import { GUARD_TOAST } from "@/lib/guard-toast";
import { useWorkspace } from "@/lib/workspace-context";

export function OrgAdminGuard({ children }: { children: ReactNode }) {
  const { isOrgAdmin } = useAuth();
  const { redirectWithGuardToast } = useWorkspace();
  const blocked = !isOrgAdmin;
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
