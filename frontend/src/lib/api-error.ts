export type ApiErrorResource =
  | "knowledge-base"
  | "document"
  | "dashboard"
  | "search"
  | "generic";

import { localizeBackendError } from "./localize";

const NOT_FOUND_LITERAL = "Not Found";

export function isNotFoundDetail(detail: string): boolean {
  return detail === NOT_FOUND_LITERAL || detail.toLowerCase() === "not found";
}

export function normalizeDetailMessage(
  detail: string,
  _status: number,
  resource: ApiErrorResource = "generic",
): string {
  if (!isNotFoundDetail(detail)) return detail;
  switch (resource) {
    case "knowledge-base":
      return "资料库不存在";
    case "document":
      return "文档不存在";
    case "dashboard":
      return "无法加载统计数据，请稍后重试";
    case "search":
      return "搜索服务不可用，请稍后重试";
    default:
      return "未找到资源";
  }
}

export function statusFallbackMessage(
  status: number,
  resource: ApiErrorResource = "generic",
): string | null {
  if (status === 401) return "登录已过期，请重新登录";
  if (status === 403) return "没有权限执行此操作";
  if (status === 404) {
    return normalizeDetailMessage(NOT_FOUND_LITERAL, 404, resource);
  }
  if (status === 409 && resource === "knowledge-base") {
    return "该名称的资料库已存在，请换一个名称";
  }
  return null;
}

export async function readApiErrorDetail(
  res: Response,
): Promise<string | null> {
  try {
    const data = (await res.json()) as {
      detail?: string | { msg?: string }[];
    };
    if (typeof data.detail === "string") return localizeBackendError(data.detail);
    if (Array.isArray(data.detail)) {
      return data.detail.map((item) => item.msg ?? "请求参数无效").join("；");
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function getRequestPath(res: Response): string {
  try {
    return new URL(res.url).pathname;
  } catch {
    return "";
  }
}
