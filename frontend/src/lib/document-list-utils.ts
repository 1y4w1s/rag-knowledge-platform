import type { Document } from "@/lib/document-api";

export type DocumentSortMode = "uploaded_at_desc" | "filename_asc";

export function parseDocumentQuery(search: string): string {
  return new URLSearchParams(search).get("q")?.trim() ?? "";
}

export function buildUrlWithoutDocumentQuery(
  pathname: string,
  search: string,
): string {
  const params = new URLSearchParams(search);
  params.delete("q");
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function buildUrlWithDocumentQuery(
  pathname: string,
  search: string,
  query: string,
): string {
  const params = new URLSearchParams(search);
  const trimmed = query.trim();
  if (trimmed) {
    params.set("q", trimmed);
  } else {
    params.delete("q");
  }
  const next = params.toString();
  return next ? `${pathname}?${next}` : pathname;
}

export function filterDocumentsByQuery(
  documents: Document[] | null | undefined,
  query: string,
): Document[] {
  const list = documents ?? [];
  const needle = query.trim().toLowerCase();
  if (!needle) return list;
  return list.filter((doc) =>
    doc.filename.toLowerCase().includes(needle),
  );
}

export function sortDocuments(
  documents: Document[] | null | undefined,
  mode: DocumentSortMode,
): Document[] {
  const sorted = [...(documents ?? [])];
  if (mode === "filename_asc") {
    sorted.sort((a, b) =>
      a.filename.localeCompare(b.filename, "zh-CN", { sensitivity: "base" }),
    );
    return sorted;
  }
  sorted.sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  return sorted;
}
