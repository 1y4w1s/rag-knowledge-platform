export const MEMBER_WRITE_BLOCKED_MESSAGE =
  "团队成员仅可查看与对话，上传、删除等写操作需联系管理员。";

export const PERMISSION_DENIED_MESSAGE =
  "没有权限执行此操作，请联系团队管理员。";

export function showMemberWriteBlockedToast(
  showToast: (message: string) => void,
): void {
  showToast(MEMBER_WRITE_BLOCKED_MESSAGE);
}
