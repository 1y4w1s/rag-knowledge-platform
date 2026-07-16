/**
 * 统一的 API 客户端。
 * 所有 API 模块统一走此入口，确保：
 * - 自动携带 Authorization 头
 * - 401 时自动跳转登录页
 */
import { getAccessToken, clearAuthSession } from "@/lib/auth-storage";

const LOGIN_PATH = "/login";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * 带 401 自动拦截的 fetch 封装。
 * 当后端返回 401 时，清除本地会话并跳转登录页。
 */
export async function apiFetch(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...init, headers });

  if (res.status === 401) {
    clearAuthSession();
    const currentPath = encodeURIComponent(
      `${window.location.pathname}${window.location.search}`,
    );
    window.location.href = `${LOGIN_PATH}?redirect=${currentPath}`;
    throw new ApiError("登录已过期，请重新登录", 401);
  }

  return res;
}

/** 解析 API 错误响应为可读消息。 */
export async function parseApiError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? body.message ?? `请求失败 (${res.status})`;
  } catch {
    return `请求失败 (${res.status})`;
  }
}

/** 带 JSON 解析的便捷 GET。 */
export async function apiGet<T>(url: string): Promise<T> {
  const res = await apiFetch(url);
  if (!res.ok) throw new ApiError(await parseApiError(res), res.status);
  return res.json() as Promise<T>;
}

/** 带 JSON body 的便捷 POST。 */
export async function apiPost<T>(
  url: string,
  body?: unknown,
): Promise<T> {
  const res = await apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new ApiError(await parseApiError(res), res.status);
  return res.json() as Promise<T>;
}
