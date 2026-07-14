import type { StoredUser } from "@/lib/auth-storage";
import { isCompanyAdmin } from "@/lib/department-align";
import { DEPARTMENT_ALL } from "@/lib/department-storage";
import { buildDepartmentTree, type DepartmentTreeNode } from "@/lib/org-unit-tree";
import type { OrgUnit } from "@/lib/org-units-api";

export type KbAffiliationMode = "current" | "public" | "specific";

export interface KbAffiliationOption {
  unitId: string;
  label: string;
  depth: number;
}

function unitAdminManagedSubtreeIds(
  units: OrgUnit[],
  adminUnitIds: Set<string>,
): Set<string> {
  const { byId: treeById } = buildDepartmentTree(units);
  const managed = new Set<string>();
  for (const adminId of adminUnitIds) {
    const node = treeById.get(adminId);
    if (!node) continue;
    const walk = (current: DepartmentTreeNode) => {
      managed.add(current.unit.id);
      current.children.forEach(walk);
    };
    walk(node);
  }
  return managed;
}

export function buildKbAffiliationOptions(
  units: OrgUnit[],
  user: StoredUser,
): KbAffiliationOption[] {
  const admin = isCompanyAdmin(user);
  const adminUnitIds = new Set(user.unit_admin_unit_ids ?? []);
  const selectableIds = admin
    ? new Set(units.map((unit) => unit.id))
    : unitAdminManagedSubtreeIds(units, adminUnitIds);

  const { root } = buildDepartmentTree(units);
  if (!root) return [];

  const options: KbAffiliationOption[] = [];
  const walk = (node: DepartmentTreeNode, depth: number) => {
    if (selectableIds.has(node.unit.id)) {
      options.push({
        unitId: node.unit.id,
        label: node.unit.name,
        depth,
      });
    }
    node.children.forEach((child) => walk(child, depth + 1));
  };
  walk(root, 0);
  return options;
}

export function canSelectCompanyPublicKb(user: StoredUser): boolean {
  return isCompanyAdmin(user);
}

export function resolveCurrentDepartmentAffiliation(
  departmentId: string | null,
): string | null {
  if (!departmentId || departmentId === DEPARTMENT_ALL) return null;
  return departmentId;
}

export function formatAffiliationOptionLabel(option: KbAffiliationOption): string {
  return `${"　".repeat(option.depth)}${option.label}`;
}
