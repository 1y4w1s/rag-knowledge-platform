import { useLayoutEffect, useRef, type ReactNode } from "react";

import { GUARD_TOAST } from "@/lib/guard-toast";
import { useWorkspace } from "@/lib/workspace-context";

export function WorkspaceGuard({ children }: { children: ReactNode }) {
  const { isTeamWorkspace, redirectWithGuardToast } = useWorkspace();
  const blocked = !isTeamWorkspace;
  const handledRef = useRef(false);

  useLayoutEffect(() => {
    if (!blocked) {
      handledRef.current = false;
      return;
    }
    if (handledRef.current) return;
    handledRef.current = true;
    redirectWithGuardToast(GUARD_TOAST.T2);
  }, [blocked, redirectWithGuardToast]);

  if (blocked) return null;

  return children;
}
