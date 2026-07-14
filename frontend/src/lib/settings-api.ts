import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";
import type { AccountType, OrgRole } from "@/lib/auth-storage";

const API_BASE = "/api/v1";

export interface AccountSettings {
  id: string;
  email: string;
  username: string;
  nickname: string | null;
  account_type: AccountType;
  org_id: string | null;
  org_role: OrgRole | null;
  org_name: string | null;
}

async function parseSettingsError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return statusFallbackMessage(res.status) ?? "请求失败，请稍后重试";
}

export async function fetchAccountSettings(): Promise<AccountSettings> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/settings/account`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await parseSettingsError(res));
  return (await res.json()) as AccountSettings;
}

export async function changeAccountPassword(
  currentPassword: string,
  newPassword: string,
): Promise<string> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/settings/account`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!res.ok) throw new Error(await parseSettingsError(res));

  const data = (await res.json()) as { message?: string };
  return data.message ?? "密码已更新，请重新登录";
}

export interface JoinTeamResult {
  message: string;
  account: AccountSettings;
}

export async function joinTeamWithInviteCode(code: string): Promise<JoinTeamResult> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/settings/account/join-team`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ invite_code: code.trim() }),
  });
  if (!res.ok) throw new Error(await parseSettingsError(res));
  return (await res.json()) as JoinTeamResult;
}

export interface LeaveTeamResult {
  message: string;
  account: AccountSettings;
}

export async function leaveTeam(): Promise<LeaveTeamResult> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/settings/account/leave-team`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await parseSettingsError(res));
  return (await res.json()) as LeaveTeamResult;
}

export function formatAccountTypeLabel(settings: AccountSettings): string {
  if (settings.account_type === "personal") return "个人版";
  if (settings.org_role === "admin") return "团队版 · 管理员";
  if (settings.org_role === "member") return "团队版 · 成员";
  return "团队版";
}
