import type { StoredUser } from "@/lib/auth-storage";
import { DEPARTMENT_ALL } from "@/lib/department-storage";
import { isValidOrgWorkspaceId } from "@/lib/workspace-align";

export type DepartmentAlignResult =
  | { ok: true; departmentId: string; realigned?: boolean }
  | { ok: false; reason: "invalid" | "no_membership" | "all_forbidden" | "no_units" };

export function isCompanyAdmin(user: StoredUser): boolean {
  return Boolean(user.is_owner) || user.org_role === "admin";
}

/** 无存盘时的默认部门：主部门 → 首个兼任 → Admin 用 `all`（E9）。 */
export function resolveDefaultDepartmentId(user: StoredUser): string | null {
  if (user.primary_unit_id) return user.primary_unit_id;
  const units = user.unit_ids ?? [];
  if (units.length > 0) return units[0];
  if (isCompanyAdmin(user)) return DEPARTMENT_ALL;
  return null;
}

function unitIdsInclude(user: StoredUser, unitId: string): boolean {
  return (user.unit_ids ?? []).includes(unitId);
}

/** 校验 localStorage 部门 id 与 `/me` membership（ORG-1-2 E1/E4）。 */
export function alignDepartmentWithUser(
  stored: string | null,
  user: StoredUser,
): DepartmentAlignResult {
  if (stored === DEPARTMENT_ALL) {
    if (isCompanyAdmin(user)) {
      return { ok: true, departmentId: DEPARTMENT_ALL };
    }
    const fallback = resolveDefaultDepartmentId(user);
    if (fallback && fallback !== DEPARTMENT_ALL) {
      return { ok: true, departmentId: fallback, realigned: true };
    }
    return { ok: false, reason: "all_forbidden" };
  }

  if (stored && isValidOrgWorkspaceId(stored)) {
    // ORG PRD E6 / scope.py: 公司 Admin 可选任意部门，不必在 unit_ids 内
    if (unitIdsInclude(user, stored) || isCompanyAdmin(user)) {
      return { ok: true, departmentId: stored };
    }
    const fallback = resolveDefaultDepartmentId(user);
    if (fallback) {
      return { ok: true, departmentId: fallback, realigned: true };
    }
    return { ok: false, reason: "no_membership" };
  }

  if (stored) {
    const fallback = resolveDefaultDepartmentId(user);
    if (fallback) {
      return { ok: true, departmentId: fallback, realigned: true };
    }
    return { ok: false, reason: "invalid" };
  }

  const fallback = resolveDefaultDepartmentId(user);
  if (fallback) return { ok: true, departmentId: fallback };
  return { ok: false, reason: "no_units" };
}
