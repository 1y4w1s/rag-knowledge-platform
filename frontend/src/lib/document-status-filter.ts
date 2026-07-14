import { isDocumentProcessing, type Document } from "@/lib/document-api";
import {
  parseDocumentListFilters,
  type DocumentStatusGroup,
} from "@/lib/document-advanced-filter";

export type DocumentStatusFilter = "processing" | "failed";

export function parseStatusFilter(search: string): DocumentStatusFilter | null {
  const { statuses } = parseDocumentListFilters(search);
  if (statuses.length !== 1) return null;
  const only = statuses[0];
  if (only === "processing" || only === "failed") return only;
  return null;
}

export function parseStatusFilters(search: string): DocumentStatusGroup[] {
  return parseDocumentListFilters(search).statuses;
}

/** @deprecated Server-side filtering handles status; kept for legacy callers. */
export function filterDocumentsByStatus(
  documents: Document[],
  filter: DocumentStatusFilter | null,
): Document[] {
  if (!filter) return documents;
  if (filter === "processing") {
    return documents.filter((doc) => isDocumentProcessing(doc.status));
  }
  return documents.filter((doc) => doc.status === "failed");
}
export function getStatusFilterLabel(filter: DocumentStatusFilter): string {
  return filter === "processing" ? "整理中" : "失败";
}

export function buildUrlWithoutStatusFilter(
  pathname: string,
  search: string,
): string {
  const params = new URLSearchParams(search);
  params.delete("status");
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}