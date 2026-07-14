import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";
import type { OrgRole } from "@/lib/auth-storage";

const API_BASE = "/api/v1";

export interface OrganizationSettings {
  id: string;
  name: string;
  created_at: string;
  member_count: number;
}

export interface OrganizationMember {
  user_id: string;
  email: string;
  role: OrgRole;
  is_owner: boolean;
  joined_at: string;
}

export interface OrganizationInvite {
  code: string;
  org_id: string;
  expires_at: string | null;
  created_at: string;
}

async function parseOrgError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return statusFallbackMessage(res.status) ?? "请求失败，请稍后重试";
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
}

export async function fetchOrganizationSettings(): Promise<OrganizationSettings> {
  const res = await fetch(`${API_BASE}/organization/settings`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OrganizationSettings;
}

export async function updateOrganizationName(name: string): Promise<OrganizationSettings> {
  const res = await fetch(`${API_BASE}/organization/settings`, {
    method: "PATCH",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OrganizationSettings;
}

export async function fetchOrganizationMembers(): Promise<OrganizationMember[]> {
  const res = await fetch(`${API_BASE}/organization/members`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  const data = (await res.json()) as { items: OrganizationMember[] };
  return data.items;
}

export async function addOrganizationMember(email: string): Promise<OrganizationMember> {
  const res = await fetch(`${API_BASE}/organization/members`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email: email.trim() }),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OrganizationMember;
}

export async function removeOrganizationMember(userId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/organization/members/${userId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
}

export async function updateOrganizationMemberRole(
  userId: string,
  role: Extract<OrgRole, "admin" | "member">,
): Promise<OrganizationMember> {
  const res = await fetch(`${API_BASE}/organization/members/${userId}`, {
    method: "PATCH",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OrganizationMember;
}

export interface OwnershipTransferResult {
  previous_owner: OrganizationMember;
  new_owner: OrganizationMember;
}

export async function transferOrganizationOwnership(
  targetUserId: string,
): Promise<OwnershipTransferResult> {
  const res = await fetch(`${API_BASE}/organization/transfer-ownership`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ target_user_id: targetUserId }),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OwnershipTransferResult;
}

export async function createOrganizationInvite(): Promise<OrganizationInvite> {
  const res = await fetch(`${API_BASE}/organization/invites`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await parseOrgError(res));
  return (await res.json()) as OrganizationInvite;
}

export function formatInviteExpiry(expiresAt: string | null): string {
  if (!expiresAt) return "永久有效";
  const date = new Date(expiresAt);
  return `有效期至 ${date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })}`;
}

export function formatOrgRoleLabel(role: OrgRole, isOwner = false): string {
  if (isOwner) return "所有者";
  return role === "admin" ? "管理员" : "成员";
}

export function formatJoinedAt(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatCreatedAt(iso: string): string {
  return formatJoinedAt(iso);
}
