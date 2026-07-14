import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { isAuthenticated } from "@/lib/auth-storage";
import { useDepartment } from "@/lib/department-context";
import { fetchKnowledgeBases } from "@/lib/knowledge-base-api";
import { useWorkspace } from "@/lib/workspace-context";
import { getRecentKbId } from "@/lib/workspace-storage";

export { getRecentKbId, persistRecentKbId } from "@/lib/workspace-storage";

export function kbIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/knowledge-bases\/([^/]+)/);
  return match?.[1] ?? null;
}

/** 侧栏「对话」链接：当前路由 KB > 当前 workspace 分键 > 列表首库。 */
export function useSidebarChatKbId(): string | null {
  const { pathname } = useLocation();
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const routeKbId = kbIdFromPath(pathname);
  const [fallbackKbId, setFallbackKbId] = useState<string | null>(null);

  useEffect(() => {
    if (routeKbId) return;

    const stored = getRecentKbId(workspace);
    if (stored) {
      setFallbackKbId(stored);
      return;
    }

    if (!isAuthenticated()) {
      setFallbackKbId(null);
      return;
    }

    let cancelled = false;
    const expectedGen = generation;
    const expectedDeptGen = departmentGeneration;

    void fetchKnowledgeBases({
      expectedGen,
      getCurrentGeneration: getGeneration,
      expectedDepartmentGen: expectedDeptGen,
      getCurrentDepartmentGeneration: getDepartmentGeneration,
      workspace,
      departmentId: workspace === "personal" ? null : departmentId,
    })
      .then((list) => {
        if (cancelled || list === null) return;
        if (getGeneration() !== expectedGen) return;
        if (getDepartmentGeneration() !== expectedDeptGen) return;
        setFallbackKbId(list[0]?.id ?? null);
      })
      .catch(() => {
        if (!cancelled) setFallbackKbId(null);
      });

    return () => {
      cancelled = true;
    };
  }, [
    routeKbId,
    workspace,
    generation,
    getGeneration,
    departmentId,
    departmentGeneration,
    getDepartmentGeneration,
  ]);

  return routeKbId ?? fallbackKbId;
}
