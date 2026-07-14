/** 审计 action → 中文标签（与 backend write_audit_log 事件对齐） */

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "登录成功",
  "auth.login_failed": "登录失败",
  "kb.delete": "删除资料库",
  "document.upload": "上传文档",
  "document.delete": "删除文档",
  "document.retry": "重试文档",
  "org.member_add": "添加成员",
  "org.member_remove": "移除成员",
  "org.role_change": "变更角色",
  "org_unit.create": "创建部门",
  "org_unit.rename": "重命名部门",
  "org_unit.delete": "删除部门",
  "org_unit.member_add": "部门添加成员",
  "org_unit.member_remove": "部门移除成员",
  "org_unit.member_update": "更新部门成员",
  "storage.cleanup_failed": "磁盘清理失败",
};

export const AUDIT_ACTION_OPTIONS = Object.entries(ACTION_LABELS).map(
  ([value, label]) => ({ value, label }),
);

export const FAILED_AUDIT_ACTIONS = new Set<string>([
  "auth.login_failed",
  "storage.cleanup_failed",
]);

export function isFailedAuditAction(action: string): boolean {
  return FAILED_AUDIT_ACTIONS.has(action);
}

export function formatAuditAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}
