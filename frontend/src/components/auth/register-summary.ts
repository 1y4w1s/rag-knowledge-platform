/** 注册向导 · 摘要 chip 文案 */

export function formatRegisterSummaryChip(input: {
  usage: "personal" | "team";
  teamRole: "creator" | "member" | null;
  orgName: string;
  inviteCode: string;
  resolvedOrgName?: string;
}): string {
  if (input.usage === "personal") return "个人 · 我的空间";

  if (input.teamRole === "creator") {
    const name = input.orgName.trim() || "新团队";
    return `团队 · 创建者 · ${name}`;
  }

  if (input.teamRole === "member") {
    const teamName = input.resolvedOrgName?.trim();
    if (teamName) return `成员 · ${teamName}`;
    const code = input.inviteCode.trim().toUpperCase();
    if (!code) return "成员 · 凭邀请码加入";
    if (code.length <= 14) return `成员 · 邀请码 ${code}`;
    return `成员 · 邀请码 ${code.slice(0, 10)}…`;
  }

  return "团队";
}

export function registerCredentialsSubtitle(input: {
  usage: "personal" | "team";
  teamRole: "creator" | "member" | null;
}): string {
  if (input.usage === "personal") {
    return "完成以下信息即可创建个人账号，默认使用「我的空间」。";
  }
  if (input.teamRole === "member") {
    return "填写登录信息；提交时会再次校验邀请码并加入团队。";
  }
  return "注册成功后默认进入团队空间，可随时切回「我的空间」。";
}

export function teamRoleStepSubtitle(
  teamRole: "creator" | "member" | null,
): string {
  if (teamRole === "creator") {
    return "填写团队显示名称；创建后你将成为管理员。";
  }
  if (teamRole === "member") {
    return "向团队管理员索取邀请码；无效或过期将无法完成注册。";
  }
  return "选择创建新团队，或凭邀请码加入已有团队。";
}
