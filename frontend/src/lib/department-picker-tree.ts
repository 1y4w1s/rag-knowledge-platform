import type { StoredUser } from "@/lib/auth-storage";
import { isCompanyAdmin } from "@/lib/department-align";
import { DEPARTMENT_ALL } from "@/lib/department-storage";
import { formatOrgLabel } from "@/lib/format-org-label";
import { buildDepartmentTree, type DepartmentTreeNode } from "@/lib/org-unit-tree";
import type { OrgUnit } from "@/lib/org-units-api";

export interface DepartmentPickerModel {
  root: DepartmentTreeNode | null;
  byId: Map<string, DepartmentTreeNode>;
  selectableIds: Set<string>;
  showAllScopeOption: boolean;
}

export function buildDepartmentPickerModel(
  units: OrgUnit[],
  user: StoredUser,
): DepartmentPickerModel {
  const { root, byId } = buildDepartmentTree(units);
  const admin = isCompanyAdmin(user);
  const memberIds = new Set(user.unit_ids ?? []);

  const selectableIds = admin
    ? new Set(units.map((unit) => unit.id))
    : memberIds;

  return {
    root,
    byId,
    selectableIds,
    showAllScopeOption: admin,
  };
}

export function resolveDepartmentShortLabel(options: {
  departmentId: string | null;
  unitsById: Map<string, OrgUnit>;
  loading: boolean;
}): string {
  const { departmentId, unitsById, loading } = options;
  if (loading) return "…";
  if (!departmentId) return "未分配";
  if (departmentId === DEPARTMENT_ALL) return "全公司";

  const unit = unitsById.get(departmentId);
  if (!unit) return "…";
  return formatOrgLabel(unit.name);
}

export function isDepartmentScopeSelected(
  departmentId: string | null,
  optionId: string,
): boolean {
  return departmentId === optionId;
}
