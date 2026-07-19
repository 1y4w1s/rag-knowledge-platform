const WORKSPACE_KEY = "zhian-workspace";
const LEGACY_RECENT_KEY = "zhian-recent-kb-id";
const RECENT_KB_PREFIX = "zhian-recent-kb:";

/** `personal` or organization UUID string */
export type WorkspaceId = "personal" | string;

export function getStoredWorkspace(): WorkspaceId {
  const raw = localStorage.getItem(WORKSPACE_KEY);
  if (!raw || raw.trim() === "") return "personal";
  return raw.trim();
}

export function setStoredWorkspace(workspace: WorkspaceId): void {
  localStorage.setItem(WORKSPACE_KEY, workspace);
}

export function clearStoredWorkspace(): void {
  localStorage.removeItem(WORKSPACE_KEY);
}

export function recentKbKey(workspace: WorkspaceId): string {
  return workspace === "personal"
    ? `${RECENT_KB_PREFIX}personal`
    : `${RECENT_KB_PREFIX}${workspace}`;
}

export function getRecentKbId(workspace?: WorkspaceId): string | null {
  try {
    const key = recentKbKey(workspace ?? getStoredWorkspace());
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function persistRecentKbId(id: string, workspace?: WorkspaceId): void {
  try {
    const key = recentKbKey(workspace ?? getStoredWorkspace());
    localStorage.setItem(key, id);
  } catch {
    /* ignore quota / private mode */
  }
}

/** 删库后清当前 workspace 的 recent 键（WS-2-2 E8） */
export function clearRecentKbId(workspace?: WorkspaceId): void {
  try {
    const key = recentKbKey(workspace ?? getStoredWorkspace());
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** Copy legacy single key → personal分键，然后删除旧键（H11）。 */
export function migrateLegacyRecentKbKey(): void {
  try {
    const legacy = localStorage.getItem(LEGACY_RECENT_KEY);
    if (!legacy) return;

    const personalKey = recentKbKey("personal");
    if (!localStorage.getItem(personalKey)) {
      localStorage.setItem(personalKey, legacy);
    }
    localStorage.removeItem(LEGACY_RECENT_KEY);
  } catch {
    /* ignore */
  }
}

export function clearWorkspaceAndRecentKeys(): void {
  try {
    localStorage.removeItem(WORKSPACE_KEY);
    localStorage.removeItem(LEGACY_RECENT_KEY);

    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(RECENT_KB_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    for (const key of keysToRemove) {
      localStorage.removeItem(key);
    }
  } catch {
    /* ignore */
  }
}

/** Login / register：清 workspace + recent，回落 personal（E10）。 */
export function prepareWorkspaceForLogin(): void {
  clearWorkspaceAndRecentKeys();
  setStoredWorkspace("personal");
}

/** Append `?workspace=` (or `&workspace=`) for list/stats/create calls (H9). */
export function appendWorkspaceQuery(
  url: string,
  workspace?: WorkspaceId,
): string {
  const ws = workspace ?? getStoredWorkspace();
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}workspace=${encodeURIComponent(ws)}`;
}
