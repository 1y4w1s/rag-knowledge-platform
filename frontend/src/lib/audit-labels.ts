/** 审计 action → 中文标签（与 backend write_audit_log 事件对齐） */

const ACTION_LABELS: Record<string, string> = {
  "auth.login": "登录成功",
  "auth.login_failed": "登录失败",
  "auth.login_rate_limited": "登录限流",
  "auth.ip_rate_limited": "IP 限流",
  "kb.delete": "删除资料库",
  "kb.grant.create": "授权共享",
  "kb.grant.delete": "取消共享",
  "document.upload": "上传文档",
  "document.delete": "删除文档",
  "document.retry": "重试文档",
  "document.version.restore": "恢复文档版本",
  "org.member_add": "添加成员",
  "org.member_remove": "移除成员",
  "org.role_change": "变更角色",
  "org.dissolve": "解散团队",
  "org_unit.create": "创建部门",
  "org_unit.rename": "重命名部门",
  "org_unit.delete": "删除部门",
  "org_unit.member_add": "部门添加成员",
  "org_unit.member_remove": "部门移除成员",
  "org_unit.member_update": "更新部门成员",
  "chat.thread_created": "创建对话",
  "chat.thread_archived": "归档对话",
  "chat.message_sent": "发送消息",
  "agent.run_started": "Agent 开始执行",
  "agent.tool_executed": "Agent 工具执行",
  "agent.tool_denied": "Agent 工具拒绝",
  "agent.run_completed": "Agent 执行完成",
  "agent.approval_created": "Agent 待审批",
  "agent.approval_adopted": "Agent 审批通过",
  "agent.approval_cancelled": "Agent 审批取消",
  "agent.approval_denied": "Agent 审批拒绝",
  "storage.cleanup_failed": "磁盘清理失败",
};

export const AUDIT_ACTION_OPTIONS = Object.entries(ACTION_LABELS)
  .map(([value, label]) => ({ value, label }))
  .sort((a, b) => a.label.localeCompare(b.label, "zh-CN"));

export const FAILED_AUDIT_ACTIONS = new Set<string>([
  "auth.login_failed",
  "auth.login_rate_limited",
  "auth.ip_rate_limited",
  "storage.cleanup_failed",
  "agent.tool_denied",
  "agent.approval_denied",
]);

export function isFailedAuditAction(action: string): boolean {
  return FAILED_AUDIT_ACTIONS.has(action);
}

export function formatAuditAction(action: string): string {
  return ACTION_LABELS[action] ?? action;
}
