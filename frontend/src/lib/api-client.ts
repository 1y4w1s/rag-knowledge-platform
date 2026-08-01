/**
 * 统一的 API 客户端。
 * 所有 API 模块统一走此入口，确保：
 * - 自动携带 Authorization 头
 * - 401 时自动跳转登录页
 * - 可重试错误（网络错误 / 429 / 5xx）自动指数退避重试
 */
import { getAccessToken, clearAuthSession } from "@/lib/auth-storage";

const LOGIN_PATH = "/login";

// ── 重试配置 ─────────────────────────────────────────────────────────

const MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 10000;

/** 判断 HTTP 状态码是否可重试。 */
function isRetryableStatus(status: number): boolean {
  // 429 Too Many Requests — 可重试
  if (status === 429) return true;
  // 5xx — 可重试
  if (status >= 500 && status < 600) return true;
  return false;
}

/** 带 jitter 的指数退避延时（毫秒）。 */
function backoffDelay(attempt: number): number {
  const delay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  const jitter = Math.random() * delay * 0.2 - delay * 0.1; // ±10%
  return Math.round(Math.max(0, delay + jitter));
}

/** sleep 辅助。 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * 带指数退避重试的 fetch 核心。
 *
 * 对可重试错误（网络异常 / 429 / 5xx）自动重试，其余错误直接抛出。
 */
async function retryFetch(
  url: string,
  init?: RequestInit,
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url, init);

      // 401 特殊处理：清除会话并跳转
      if (res.status === 401) {
        clearAuthSession();
        const currentPath = encodeURIComponent(
          `${window.location.pathname}${window.location.search}`,
        );
        window.location.href = `${LOGIN_PATH}?redirect=${currentPath}`;
        throw new ApiError("登录已过期，请重新登录", 401);
      }

      // 不可重试 → 直接返回
      if (res.ok || !isRetryableStatus(res.status)) {
        return res;
      }

      // 可重试 — 记录并继续重试循环
      lastError = new ApiError(`请求失败 (${res.status})`, res.status);

      if (attempt < MAX_RETRIES) {
        const delay = backoffDelay(attempt);
        console.warn(
          `[api-client] 请求失败 ${res.status}，第 ${attempt + 1}/${MAX_RETRIES} 次重试，等待 ${delay}ms`,
          url,
        );
        await sleep(delay);
      }
    } catch (err) {
      // 网络错误（fetch 抛出）— 可重试
      lastError = err instanceof Error ? err : new Error(String(err));

      // 忽略 401 已抛出的 ApiError
      if (lastError instanceof ApiError && (lastError as ApiError).status === 401) {
        throw lastError;
      }

      if (attempt < MAX_RETRIES) {
        const delay = backoffDelay(attempt);
        console.warn(
          `[api-client] 网络错误，第 ${attempt + 1}/${MAX_RETRIES} 次重试，等待 ${delay}ms`,
          url,
          lastError.message,
        );
        await sleep(delay);
      }
    }
  }

  throw lastError ?? new Error("请求失败（重试耗尽）");
}

/**
 * 带 401 自动拦截 + 指数退避重试的 fetch 封装。
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

  return retryFetch(url, { ...init, headers });
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
