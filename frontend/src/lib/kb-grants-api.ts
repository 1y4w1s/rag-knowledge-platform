import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";

const API_BASE = "/api/v1";

export type GranteeType = "org_unit" | "company";
export type GrantPermission = "read" | "write";

export interface KbGrant {
  id: string;
  kb_id: string;
  grantee_type: GranteeType;
  grantee_id: string | null;
  permission: GrantPermission;
  created_at: string;
}

export interface KbGrantCreateInput {
  grantee_type: GranteeType;
  grantee_id?: string | null;
  permission?: GrantPermission;
}

async function parseGrantsError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return statusFallbackMessage(res.status) ?? "请求失败，请稍后重试";
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function fetchKbGrants(kbId: string): Promise<KbGrant[]> {
  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/grants`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseGrantsError(res));
  const data = (await res.json()) as { items?: KbGrant[] };
  return Array.isArray(data.items) ? data.items : [];
}

export async function createKbGrant(
  kbId: string,
  input: KbGrantCreateInput,
): Promise<KbGrant> {
  const body: Record<string, string | null> = {
    grantee_type: input.grantee_type,
    permission: input.permission ?? "read",
  };
  if (input.grantee_id !== undefined) {
    body.grantee_id = input.grantee_id;
  }

  const res = await fetch(`${API_BASE}/knowledge-bases/${kbId}/grants`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseGrantsError(res));
  return (await res.json()) as KbGrant;
}

export async function deleteKbGrant(kbId: string, grantId: string): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(
    `${API_BASE}/knowledge-bases/${kbId}/grants/${grantId}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!res.ok) throw new Error(await parseGrantsError(res));
}

export function formatGrantPermissionLabel(permission: GrantPermission): string {
  return permission === "write" ? "读写" : "只读";
}
