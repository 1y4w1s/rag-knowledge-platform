import type { KnowledgeBase } from "@/lib/knowledge-base-api";

export type KbListSortField =
  | "updated_at"
  | "name"
  | "doc_count"
  | "needs_attention";

export type KbListSortMode =
  | "updated_at_desc"
  | "updated_at_asc"
  | "name_asc"
  | "name_desc"
  | "doc_count_desc"
  | "doc_count_asc"
  | "needs_attention"
  | "healthy_first";

export const DEFAULT_KB_LIST_SORT: KbListSortMode = "updated_at_desc";
export const KB_LIST_PAGE_SIZE = 24;

const VALID_SORT_MODES = new Set<KbListSortMode>([
  "updated_at_desc",
  "updated_at_asc",
  "name_asc",
  "name_desc",
  "doc_count_desc",
  "doc_count_asc",
  "needs_attention",
  "healthy_first",
]);

const SORT_FIELD_CONFIG: {
  field: KbListSortField;
  modes: [KbListSortMode, KbListSortMode];
  labels: [string, string];
}[] = [
  {
    field: "updated_at",
    modes: ["updated_at_desc", "updated_at_asc"],
    labels: ["最近更新 ↓", "最近更新 ↑"],
  },
  {
    field: "name",
    modes: ["name_asc", "name_desc"],
    labels: ["名称 A→Z", "名称 Z→A"],
  },
  {
    field: "doc_count",
    modes: ["doc_count_desc", "doc_count_asc"],
    labels: ["文档数 ↓", "文档数 ↑"],
  },
  {
    field: "needs_attention",
    modes: ["needs_attention", "healthy_first"],
    labels: ["需关注", "最省心"],
  },
];

export const KB_LIST_SORT_FIELDS = SORT_FIELD_CONFIG.map(({ field }) => field);

export function getKbListSortField(mode: KbListSortMode): KbListSortField {
  const entry = SORT_FIELD_CONFIG.find((item) => item.modes.includes(mode));
  return entry?.field ?? "updated_at";
}

export function getKbListSortLabel(mode: KbListSortMode): string {
  for (const item of SORT_FIELD_CONFIG) {
    const index = item.modes.indexOf(mode);
    if (index >= 0) return item.labels[index];
  }
  return "最近更新 ↓";
}

export function getKbListSortPillLabel(
  field: KbListSortField,
  activeMode: KbListSortMode,
): string {
  const item = SORT_FIELD_CONFIG.find((entry) => entry.field === field);
  if (!item) return field;
  if (getKbListSortField(activeMode) !== field) {
    return item.labels[0];
  }
  const index = item.modes.indexOf(activeMode);
  return item.labels[index >= 0 ? index : 0];
}

/** 点当前 pill → 取反；点其它 pill → 该维度默认方向。 */
export function toggleKbListSort(
  current: KbListSortMode,
  field: KbListSortField,
): KbListSortMode {
  const item = SORT_FIELD_CONFIG.find((entry) => entry.field === field);
  if (!item) return DEFAULT_KB_LIST_SORT;

  if (getKbListSortField(current) === field) {
    const index = item.modes.indexOf(current);
    return item.modes[index === 0 ? 1 : 0];
  }
  return item.modes[0];
}

export function parseKbListQuery(search: string): string {
  return new URLSearchParams(search).get("q")?.trim() ?? "";
}

export function parseKbListSort(search: string): KbListSortMode {
  const raw = new URLSearchParams(search).get("sort")?.trim();
  if (raw && VALID_SORT_MODES.has(raw as KbListSortMode)) {
    return raw as KbListSortMode;
  }
  return DEFAULT_KB_LIST_SORT;
}

export function parseKbListPage(search: string): number {
  const raw = new URLSearchParams(search).get("page");
  if (!raw) return 1;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
}

function resetKbListPageParam(params: URLSearchParams): void {
  params.delete("page");
}

export function buildUrlWithoutKbListQuery(
  pathname: string,
  search: string,
): string {
  const params = new URLSearchParams(search);
  params.delete("q");
  resetKbListPageParam(params);
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function buildUrlWithKbListQuery(
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
  resetKbListPageParam(params);
  const next = params.toString();
  return next ? `${pathname}?${next}` : pathname;
}

export function buildUrlWithKbListSort(
  pathname: string,
  search: string,
  sortMode: KbListSortMode,
): string {
  const params = new URLSearchParams(search);
  if (sortMode === DEFAULT_KB_LIST_SORT) {
    params.delete("sort");
  } else {
    params.set("sort", sortMode);
  }
  resetKbListPageParam(params);
  const next = params.toString();
  return next ? `${pathname}?${next}` : pathname;
}

export function buildUrlWithKbListPage(
  pathname: string,
  search: string,
  page: number,
): string {
  const params = new URLSearchParams(search);
  if (page <= 1) {
    params.delete("page");
  } else {
    params.set("page", String(page));
  }
  const next = params.toString();
  return next ? `${pathname}?${next}` : pathname;
}

function kbUpdatedAtMs(kb: KnowledgeBase): number {
  return new Date(kb.updated_at ?? kb.created_at).getTime();
}

function attentionRank(kb: KnowledgeBase): number {
  if (kb.failed_count > 0) return 0;
  if (kb.processing_count > 0) return 1;
  return 2;
}

export function filterKnowledgeBases(
  items: KnowledgeBase[],
  query: string,
): KnowledgeBase[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return items;
  return items.filter((kb) => {
    const name = kb.name.toLowerCase();
    const description = (kb.description ?? "").toLowerCase();
    return name.includes(needle) || description.includes(needle);
  });
}

export function sortKnowledgeBases(
  items: KnowledgeBase[],
  mode: KbListSortMode,
): KnowledgeBase[] {
  const sorted = [...items];
  switch (mode) {
    case "updated_at_asc":
      sorted.sort((a, b) => kbUpdatedAtMs(a) - kbUpdatedAtMs(b));
      break;
    case "name_asc":
      sorted.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
      break;
    case "name_desc":
      sorted.sort((a, b) => b.name.localeCompare(a.name, "zh-CN"));
      break;
    case "doc_count_desc":
      sorted.sort((a, b) => {
        const diff = (b.document_count ?? 0) - (a.document_count ?? 0);
        return diff !== 0 ? diff : kbUpdatedAtMs(b) - kbUpdatedAtMs(a);
      });
      break;
    case "doc_count_asc":
      sorted.sort((a, b) => {
        const diff = (a.document_count ?? 0) - (b.document_count ?? 0);
        return diff !== 0 ? diff : kbUpdatedAtMs(a) - kbUpdatedAtMs(b);
      });
      break;
    case "healthy_first":
      sorted.sort((a, b) => {
        const diff = attentionRank(b) - attentionRank(a);
        return diff !== 0 ? diff : kbUpdatedAtMs(a) - kbUpdatedAtMs(b);
      });
      break;
    case "needs_attention":
      sorted.sort((a, b) => {
        const diff = attentionRank(a) - attentionRank(b);
        return diff !== 0 ? diff : kbUpdatedAtMs(b) - kbUpdatedAtMs(a);
      });
      break;
    case "updated_at_desc":
    default:
      sorted.sort((a, b) => kbUpdatedAtMs(b) - kbUpdatedAtMs(a));
      break;
  }
  return sorted;
}
