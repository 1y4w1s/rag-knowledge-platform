import type { StoredUser } from "@/lib/auth-storage";
import type { WorkspaceId } from "@/lib/workspace-storage";

const ORG_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isValidOrgWorkspaceId(value: string): boolean {
  return ORG_UUID_RE.test(value);
}

export type WorkspaceAlignResult =
  | { ok: true; workspace: WorkspaceId }
  | { ok: false; reason: "invalid_uuid" | "no_membership" | "personal_user" };

/** Validate stored workspace against `/me` (WS-2-1 E3). */
export function alignWorkspaceWithUser(
  stored: WorkspaceId,
  user: StoredUser,
): WorkspaceAlignResult {
  if (stored === "personal") {
    return { ok: true, workspace: "personal" };
  }

  if (!isValidOrgWorkspaceId(stored)) {
    return { ok: false, reason: "invalid_uuid" };
  }

  if (user.account_type === "personal") {
    return { ok: false, reason: "personal_user" };
  }

  if (!user.org_id || user.org_id !== stored) {
    return { ok: false, reason: "no_membership" };
  }

  return { ok: true, workspace: stored };
}
