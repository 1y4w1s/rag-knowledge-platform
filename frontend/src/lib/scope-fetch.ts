import type { WorkspaceId } from "@/lib/workspace-storage";
import { appendWorkspaceQuery, getStoredWorkspace } from "@/lib/workspace-storage";
import {
  isStaleWorkspaceGeneration,
  type WorkspaceGenerationOptions,
} from "@/lib/workspace-generation";

/** Workspace + department generation and query params for scoped list/stats/search (ORG-1-6 §5.3 · ORG-3.3). */
export interface ScopeFetchOptions extends WorkspaceGenerationOptions {
  expectedDepartmentGen?: number;
  getCurrentDepartmentGeneration?: () => number;
  /** Team workspace only; personal → omitted from URL */
  departmentId?: string | null;
}

/** True when workspace or department generation changed since the request started. */
export function isStaleScopeFetch(
  options: ScopeFetchOptions | undefined,
): boolean {
  if (!options) return false;
  if (isStaleWorkspaceGeneration(options)) return true;
  if (
    options.expectedDepartmentGen !== undefined &&
    options.getCurrentDepartmentGeneration
  ) {
    return (
      options.getCurrentDepartmentGeneration() !== options.expectedDepartmentGen
    );
  }
  return false;
}

/** Append `workspace` + team-only `department_id` query params (explicit context values). */
export function appendScopeQuery(
  url: string,
  options?: Pick<ScopeFetchOptions, "workspace" | "departmentId">,
): string {
  const workspace = options?.workspace;
  let result = appendWorkspaceQuery(url, workspace);

  const effectiveWorkspace: WorkspaceId = workspace ?? getStoredWorkspace();
  if (effectiveWorkspace === "personal") {
    return result;
  }

  const departmentId = options?.departmentId;
  if (departmentId != null && departmentId !== "") {
    const separator = result.includes("?") ? "&" : "?";
    result = `${result}${separator}department_id=${encodeURIComponent(departmentId)}`;
  }

  return result;
}
