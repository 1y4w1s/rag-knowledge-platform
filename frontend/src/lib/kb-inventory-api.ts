import { getAccessToken } from "@/lib/auth-storage";
import {
  normalizeDetailMessage,
  readApiErrorDetail,
  statusFallbackMessage,
} from "@/lib/api-error";

const API_BASE = "/api/v1";

export type KbInventoryExportFormat = "csv" | "json";

export interface KbInventoryExportQuery {
  format: KbInventoryExportFormat;
  kb_id?: string;
  include_trash?: boolean;
}

async function parseInventoryError(res: Response): Promise<string> {
  const detail = await readApiErrorDetail(res);
  if (detail) {
    return normalizeDetailMessage(detail, res.status, "generic");
  }
  return statusFallbackMessage(res.status) ?? "无法导出资产清单，请稍后重试";
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
}

/** 下载知识库文档 metadata 清单（NW-38 API；服务端最多 5000 行）。 */
export async function downloadKbInventoryExport(
  query: KbInventoryExportQuery,
): Promise<void> {
  const params = new URLSearchParams();
  params.set("format", query.format);
  if (query.kb_id) params.set("kb_id", query.kb_id);
  if (query.include_trash) params.set("include_trash", "true");

  const url = `${API_BASE}/admin/kb-inventory/export?${params.toString()}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseInventoryError(res));

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download =
    query.format === "json" ? "kb-inventory.json" : "kb-inventory.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
