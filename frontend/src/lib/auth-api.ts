import {
  getAccessToken,
  saveAuthSession,
  type AccountType,
  type StoredUser,
} from "@/lib/auth-storage";

const API_BASE = "/api/v1";

export interface AuthSession {
  accessToken: string;
  user: StoredUser;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: StoredUser;
}

interface RegisterResponse {
  user: StoredUser;
}

async function parseApiError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg ?? "请求参数无效").join("；");
    }
  } catch {
    /* ignore */
  }
  if (res.status === 401) return "用户名/邮箱或密码错误";
  if (res.status === 409) return "该邮箱或用户名已被使用";
  return "请求失败，请稍后重试";
}

export async function fetchCurrentUser(): Promise<StoredUser> {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as StoredUser;
}

export async function login(
  identifier: string,
  password: string,
): Promise<AuthSession> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier, password }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));

  const data = (await res.json()) as LoginResponse;
  const session = { accessToken: data.access_token, user: data.user };
  saveAuthSession(session.accessToken, session.user);
  return session;
}

export async function register(
  email: string,
  username: string,
  password: string,
  accountType: AccountType,
  orgName?: string,
  nickname?: string,
  inviteCode?: string,
): Promise<StoredUser> {
  const body: Record<string, string> = {
    email,
    username,
    password,
    account_type: accountType,
  };
  if (nickname?.trim()) {
    body.nickname = nickname.trim();
  }
  if (accountType === "enterprise") {
    if (inviteCode?.trim()) {
      body.invite_code = inviteCode.trim();
    } else if (orgName) {
      body.org_name = orgName;
    }
  }

  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));

  const data = (await res.json()) as RegisterResponse;
  return data.user;
}

export async function registerAndLogin(
  email: string,
  username: string,
  password: string,
  accountType: AccountType,
  orgName?: string,
  nickname?: string,
  inviteCode?: string,
): Promise<AuthSession> {
  await register(
    email,
    username,
    password,
    accountType,
    orgName,
    nickname,
    inviteCode,
  );
  return login(username, password);
}

const USERNAME_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_]{2,31}$/;

export function validateUsernameClient(username: string): string | null {
  const trimmed = username.trim();
  if (!USERNAME_PATTERN.test(trimmed)) {
    return "用户名须为 3～32 位字母、数字或下划线，且以字母或数字开头";
  }
  return null;
}
