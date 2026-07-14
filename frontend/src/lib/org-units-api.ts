import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";

const API_BASE = "/api/v1";

export type UnitRole = "unit_admin" | "unit_member";

export interface OrgUnit {
  id: string;
  org_id: string;
  parent_id: string | null;
  name: string;
  depth: number;
  child_count: number;
  member_count: number;
  kb_count: number;
  created_at: string;
}

export interface OrgUnitMember {
  id: string;
  org_unit_id: string;
  user_id: string;
  email: string;
  role: UnitRole;
  is_primary: boolean;
  joined_at: string;
}

async function parseOrgUnitsError(res: Response): Promise<string> {
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

export async function fetchOrgUnits(): Promise<OrgUnit[]> {
  const res = await fetch(`${API_BASE}/org-units`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  const data = (await res.json()) as { items?: OrgUnit[] };
  return Array.isArray(data.items) ? data.items : [];
}

/** 侧栏部门选择器：Member 仅本人路径；Admin 全树（ORG-3.2）。 */
export async function fetchDepartmentPickerUnits(): Promise<OrgUnit[]> {
  const res = await fetch(`${API_BASE}/org-units/picker`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  const data = (await res.json()) as { items?: OrgUnit[] };
  return Array.isArray(data.items) ? data.items : [];
}

export async function createOrgUnit(
  name: string,
  parentId: string,
): Promise<OrgUnit> {
  const res = await fetch(`${API_BASE}/org-units`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name: name.trim(), parent_id: parentId }),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  return (await res.json()) as OrgUnit;
}

export async function updateOrgUnitName(
  unitId: string,
  name: string,
): Promise<OrgUnit> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}`, {
    method: "PATCH",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name: name.trim() }),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  return (await res.json()) as OrgUnit;
}

export async function deleteOrgUnit(unitId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
}

export async function fetchUnitMembers(unitId: string): Promise<OrgUnitMember[]> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}/members`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  const data = (await res.json()) as { items: OrgUnitMember[] };
  return data.items;
}

export async function addUnitMember(
  unitId: string,
  body: {
    user_id: string;
    role: UnitRole;
    is_primary: boolean;
  },
): Promise<OrgUnitMember> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}/members`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  return (await res.json()) as OrgUnitMember;
}

export async function updateUnitMember(
  unitId: string,
  userId: string,
  body: { role?: UnitRole; is_primary?: boolean },
): Promise<OrgUnitMember> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}/members/${userId}`, {
    method: "PATCH",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
  return (await res.json()) as OrgUnitMember;
}

export async function removeUnitMember(
  unitId: string,
  userId: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/org-units/${unitId}/members/${userId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseOrgUnitsError(res));
}

export function formatUnitRoleLabel(role: UnitRole): string {
  return role === "unit_admin" ? "部门管理员" : "部门成员";
}

export function canDeleteUnit(unit: OrgUnit): boolean {
  return unit.child_count === 0 && unit.member_count === 0 && unit.kb_count === 0;
}
