import type { SearchMode } from "@/lib/search-api";

/** 库详情 URL `search_mode=content|filename`（默认 filename）。 */
export function parseDocumentSearchMode(search: string): SearchMode {
  const raw = new URLSearchParams(search).get("search_mode");
  return raw === "content" ? "content" : "filename";
}

export function buildUrlWithDocumentSearchMode(
  pathname: string,
  search: string,
  mode: SearchMode,
): string {
  const params = new URLSearchParams(search);
  if (mode === "content") {
    params.set("search_mode", "content");
  } else {
    params.delete("search_mode");
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}
