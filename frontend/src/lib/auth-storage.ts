const TOKEN_KEY = "zhian_access_token";
const USER_KEY = "zhian_user";

export type AccountType = "personal" | "enterprise";
export type OrgRole = "admin" | "member";

export interface StoredUser {
  id: string;
  email: string;
  username: string;
  nickname: string | null;
  account_type: AccountType;
  org_id: string | null;
  org_role: OrgRole | null;
  is_owner?: boolean;
  primary_unit_id?: string | null;
  unit_ids?: string[];
  unit_admin_unit_ids?: string[];
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): StoredUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function saveAuthSession(accessToken: string, user: StoredUser): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}
