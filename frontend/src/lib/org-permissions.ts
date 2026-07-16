import type { StoredUser } from "@/lib/auth-storage";
import type { WorkspaceId } from "@/lib/workspace-storage";
import { isCompanyAdmin } from "@/lib/department-align";
/** 任一部门 unit_admin（ORG-4.1 建库） */
export function isUnitAdmin(user: StoredUser | null): boolean {
  return (user?.unit_admin_unit_ids?.length ?? 0) > 0;
}

/** 团队版普通成员（非管理员、非部门 Admin） */
export function isEnterpriseMember(user: StoredUser | null): boolean {
  return (
    user?.account_type === "enterprise" &&
    user.org_role === "member" &&
    !isUnitAdmin(user)
  );
}

/** 企业用户尚未加入任何部门（ORG-1-3 E6 · 未分配池）
 *  所有者（Owner）不受部门分配限制，永远不算未分配。 */
export function isUnassignedEnterpriseUser(user: StoredUser | null): boolean {
  if (!user || user.account_type !== "enterprise") return false;
  if (user.is_owner) return false;
  return (user.unit_ids?.length ?? 0) === 0;
}

/** 团队空间内展示未分配 Banner（Member 与无部门 Admin 均见 · E6/E9） */
export function shouldShowUnassignedBanner(
  user: StoredUser | null,
  workspace: WorkspaceId,
): boolean {
  return workspace !== "personal" && isUnassignedEnterpriseUser(user);
}

/**
 * ORG-2.5 E6：未分配 Member 不能使用建库/对话等团队业务。
 * 公司 Admin 无部门时仍可用 all scope（E9）。
 */
export function canUseTeamBusiness(
  user: StoredUser | null,
  workspace: WorkspaceId,
): boolean {
  if (workspace === "personal") return true;
  if (!user || user.account_type !== "enterprise") return true;
  if (!isUnassignedEnterpriseUser(user)) return true;
  return user.org_role === "admin";
}

/** 当前为团队工作区且用户为普通成员 → 列表/详情只读（WS-2-2 §2.2） */
export function isTeamMemberReadOnly(
  user: StoredUser | null,
  workspace: WorkspaceId,
): boolean {
  return workspace !== "personal" && isEnterpriseMember(user);
}

/**
 * 可创建/编辑/删除资料库、上传/删文档。
 * 传 workspace 时：personal 空间人人可写；团队空间仅 admin（WS-2-2）。
 */
export function canWriteKnowledgeBase(
  user: StoredUser | null,
  workspace?: WorkspaceId,
): boolean {
  if (!user) return false;

  if (workspace !== undefined) {
    if (workspace === "personal") return true;
    if (!canUseTeamBusiness(user, workspace)) return false;
    if (user.account_type === "enterprise") {
      return isCompanyAdmin(user) || isUnitAdmin(user);
    }
  }

  if (user.account_type === "personal") return true;
  return isCompanyAdmin(user) || isUnitAdmin(user);
}
