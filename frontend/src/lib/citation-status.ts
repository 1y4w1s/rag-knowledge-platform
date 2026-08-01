/** E2：引用失效对话侧文案与聚合（与 3E-3 source_status 对齐）。 */

export type CitationSourceStatus =
  | "available"
  | "document_deleted"
  | "chunk_stale"
  | "source_inaccessible";

type CitationStatusCarrier = {
  source_status?: CitationSourceStatus | null;
};

export const SOURCE_DELETED_LABEL = "源文档已删除";
export const CHUNK_STALE_LABEL = "原文片段已失效（文档已更新）";
export const SOURCE_INACCESSIBLE_LABEL =
  "该引用已不可访问（权限或资料库已变更）";
/** resolve 失败时的诚实错态（不得误标为已删除） */
export const CITATION_RESOLVE_FAILED_LABEL =
  "暂时无法校验原文状态，请稍后重试";

export const SOURCE_DELETED_CHIP_LABEL = "已删除";
export const CHUNK_STALE_CHIP_LABEL = "片段失效";
export const SOURCE_INACCESSIBLE_CHIP_LABEL = "不可访问";

export const CITATION_STALE_NOTICE_DELETED =
  "部分引用来源文档已删除；下方仍保留历史片段，原文不可再打开。";
export const CITATION_STALE_NOTICE_INACCESSIBLE =
  "部分引用当前不可访问（权限或资料库变更）。";
export const CITATION_STALE_NOTICE_CHUNK_STALE =
  "部分引用对应原文片段已失效（文档已更新）。";

export function isCitationExpandBlocked(
  citation: CitationStatusCarrier,
): boolean {
  return citation.source_status === "source_inaccessible";
}

export function isCitationChipUnavailable(
  citation: CitationStatusCarrier,
): boolean {
  return (
    citation.source_status === "source_inaccessible" ||
    citation.source_status === "document_deleted" ||
    citation.source_status === "chunk_stale"
  );
}

export function citationChipTitle(
  citation: CitationStatusCarrier,
): string | undefined {
  if (citation.source_status === "document_deleted") {
    return SOURCE_DELETED_LABEL;
  }
  if (citation.source_status === "source_inaccessible") {
    return SOURCE_INACCESSIBLE_LABEL;
  }
  if (citation.source_status === "chunk_stale") {
    return CHUNK_STALE_LABEL;
  }
  return undefined;
}

export function citationChipStatusLabel(
  citation: CitationStatusCarrier,
): string | undefined {
  if (citation.source_status === "document_deleted") {
    return SOURCE_DELETED_CHIP_LABEL;
  }
  if (citation.source_status === "source_inaccessible") {
    return SOURCE_INACCESSIBLE_CHIP_LABEL;
  }
  if (citation.source_status === "chunk_stale") {
    return CHUNK_STALE_CHIP_LABEL;
  }
  return undefined;
}

/**
 * 消息级说明：优先级 source_inaccessible > document_deleted > chunk_stale。
 */
export function citationStaleMessageNotice(
  citations: CitationStatusCarrier[],
): string | null {
  let hasInaccessible = false;
  let hasDeleted = false;
  let hasChunkStale = false;
  for (const c of citations) {
    if (c.source_status === "source_inaccessible") hasInaccessible = true;
    else if (c.source_status === "document_deleted") hasDeleted = true;
    else if (c.source_status === "chunk_stale") hasChunkStale = true;
  }
  if (hasInaccessible) return CITATION_STALE_NOTICE_INACCESSIBLE;
  if (hasDeleted) return CITATION_STALE_NOTICE_DELETED;
  if (hasChunkStale) return CITATION_STALE_NOTICE_CHUNK_STALE;
  return null;
}

export function canLinkToCitationPreview(
  citation: CitationStatusCarrier,
): boolean {
  return (
    citation.source_status !== "document_deleted" &&
    citation.source_status !== "source_inaccessible"
  );
}

export function isCitationInaccessible(
  citation: CitationStatusCarrier,
): boolean {
  return citation.source_status === "source_inaccessible";
}
