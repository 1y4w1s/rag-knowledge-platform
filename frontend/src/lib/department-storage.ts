import type { WorkspaceId } from "@/lib/workspace-storage";

const DEPARTMENT_KEY_PREFIX = "zhian-department-id:";

/** Admin-only sentinel for company-wide scope (ORG-1-2 · backend `DepartmentContext.all`). */
export const DEPARTMENT_ALL = "all" as const;

export type DepartmentScopeId = string;

export function departmentStorageKey(orgId: string): string {
  return `${DEPARTMENT_KEY_PREFIX}${orgId}`;
}

export function getStoredDepartmentId(orgId: string): string | null {
  try {
    const raw = localStorage.getItem(departmentStorageKey(orgId));
    if (!raw || raw.trim() === "") return null;
    return raw.trim();
  } catch {
    return null;
  }
}

export function setStoredDepartmentId(
  orgId: string,
  departmentId: DepartmentScopeId,
): void {
  localStorage.setItem(departmentStorageKey(orgId), departmentId);
}

export function clearStoredDepartmentId(orgId: string): void {
  try {
    localStorage.removeItem(departmentStorageKey(orgId));
  } catch {
    /* ignore */
  }
}

/** Logout / login：清全部团队空间的 department 分键（对齐 workspace E10）。 */
export function clearAllDepartmentKeys(): void {
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(DEPARTMENT_KEY_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    for (const key of keysToRemove) {
      localStorage.removeItem(key);
    }
  } catch {
    /* ignore */
  }
}

/** 个人空间不带 department；团队空间读当前 org 分键。 */
export function readDepartmentIdForWorkspace(
  workspace: WorkspaceId,
): string | null {
  if (workspace === "personal") return null;
  return getStoredDepartmentId(workspace);
}
