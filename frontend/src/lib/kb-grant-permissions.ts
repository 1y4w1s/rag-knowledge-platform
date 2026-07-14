import type { StoredUser } from "@/lib/auth-storage";
import { isCompanyAdmin } from "@/lib/department-align";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";
import { buildDepartmentTree } from "@/lib/org-unit-tree";
import type { OrgUnit } from "@/lib/org-units-api";
import type { WorkspaceId } from "@/lib/workspace-storage";

/** 是否展示库详情「共享」面板（Admin / 该库归属子树的 unit_admin · ORG-1-4）。 */
export function canManageKbGrants(
  user: StoredUser | null,
  kb: KnowledgeBase,
  workspace: WorkspaceId,
  units: OrgUnit[] | null,
): boolean {
  if (!user || workspace === "personal" || user.account_type !== "enterprise") {
    return false;
  }

  if (isCompanyAdmin(user)) return true;

  const adminUnitIds = Array.isArray(user.unit_admin_unit_ids)
    ? user.unit_admin_unit_ids
    : [];
  if (adminUnitIds.length === 0) return false;

  if (kb.org_unit_id === null) return false;

  if (!units || !Array.isArray(units) || units.length === 0) return false;

  const { byId } = buildDepartmentTree(units);
  const managed = new Set<string>();
  for (const adminId of adminUnitIds) {
    const node = byId.get(adminId);
    if (!node) continue;
    const walk = (current: typeof node) => {
      managed.add(current.unit.id);
      current.children.forEach(walk);
    };
    walk(node);
  }

  return managed.has(kb.org_unit_id);
}
