import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";
import { useDepartment } from "@/lib/department-context";
import { GUARD_TOAST } from "@/lib/guard-toast";
import {
  fetchKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";
import { useWorkspace } from "@/lib/workspace-context";
import type { WorkspaceId } from "@/lib/workspace-storage";

function kbBelongsToWorkspace(
  kb: KnowledgeBase,
  workspace: WorkspaceId,
  userId: string,
): boolean {
  if (workspace === "personal") {
    return kb.owner_user_id === userId;
  }
  return kb.owner_org_id === workspace;
}

export function ResourceGuard({ children }: { children: ReactNode }) {
  const {
    workspace,
    generation: workspaceGeneration,
    getGeneration: getWorkspaceGeneration,
    redirectWithGuardToast,
  } = useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const { user } = useAuth();
  const { id: kbId } = useParams<{ id: string }>();
  const [status, setStatus] = useState<"loading" | "ok" | "blocked">(
    "loading",
  );
  const handledRef = useRef(false);

  useEffect(() => {
    if (!kbId || !user) {
      setStatus("blocked");
      return;
    }

    let cancelled = false;
    setStatus("loading");
    handledRef.current = false;

    const expectedWorkspaceGen = workspaceGeneration;
    const expectedDepartmentGen = departmentGeneration;
    const requestWorkspace = workspace;
    const requestDepartmentId =
      workspace === "personal" ? null : departmentId;

    void fetchKnowledgeBase(kbId, {
      expectedGen: expectedWorkspaceGen,
      getCurrentGeneration: getWorkspaceGeneration,
      expectedDepartmentGen,
      getCurrentDepartmentGeneration: getDepartmentGeneration,
      workspace: requestWorkspace,
      departmentId: requestDepartmentId,
    })
      .then((kb) => {
        if (cancelled || kb === null) return;
        setStatus(
          kbBelongsToWorkspace(kb, requestWorkspace, user.id)
            ? "ok"
            : "blocked",
        );
      })
      .catch(() => {
        if (!cancelled) setStatus("blocked");
      });

    return () => {
      cancelled = true;
    };
  }, [
    kbId,
    workspace,
    workspaceGeneration,
    getWorkspaceGeneration,
    departmentId,
    departmentGeneration,
    getDepartmentGeneration,
    user,
  ]);

  useLayoutEffect(() => {
    if (status !== "blocked") {
      handledRef.current = false;
      return;
    }
    if (handledRef.current) return;
    handledRef.current = true;
    redirectWithGuardToast(GUARD_TOAST.T3);
  }, [status, redirectWithGuardToast]);

  if (status !== "ok") return null;

  return children;
}
