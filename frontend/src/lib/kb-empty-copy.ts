import type { DocumentStatusFilter } from "@/lib/document-status-filter";

/** Plan-11/2B · 筛选无结果标题（对齐 2.1 验收：「没有失败的文档」） */
export function getFilterEmptyTitle(filter: DocumentStatusFilter): string {
  return filter === "processing"
    ? "没有整理中的文档"
    : "没有失败的文档";
}

/** Plan-11/2B · 筛选无结果说明（统一句式） */
export function getFilterEmptyDescription(_filter: DocumentStatusFilter): string {
  return "清除筛选即可查看全部文档。";
}

/** Plan-11/2B · 库内文件名搜索无结果 */
export function getDocumentSearchEmptyCopy(query: string): {
  title: string;
  description: string;
} {
  return {
    title: "没有匹配的文档",
    description: `没有找到文件名包含「${query}」的文档。试试其他关键词，或清除搜索查看全部。`,
  };
}

/** R1-4 · 高级筛选无结果 */
export function getAdvancedFilterEmptyCopy(summary: string): {
  title: string;
  description: string;
} {
  return {
    title: "没有符合筛选条件的文档",
    description: summary
      ? `当前筛选：${summary}。可放宽条件或清除筛选查看全部。`
      : "可放宽条件或清除筛选查看全部。",
  };
}

/** Plan-11/2B · 资料库列表搜索无结果 */
export function getKbListSearchEmptyCopy(query: string): {
  title: string;
  description: string;
} {
  return {
    title: "没有匹配的资料库",
    description: `没有找到名称或描述包含「${query}」的资料库。试试其他关键词，或清除搜索查看全部。`,
  };
}
