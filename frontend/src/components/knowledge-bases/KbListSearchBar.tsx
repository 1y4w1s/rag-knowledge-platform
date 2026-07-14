import { Link, useNavigate } from "react-router-dom";

import { KbResultEmptyPanel } from "@/components/knowledge-bases/KbResultEmptyPanel";
import { KbSearchInput } from "@/components/knowledge-bases/KbSearchInput";
import { Button } from "@/components/ui/button";
import {
  buildUrlWithKbListQuery,
  buildUrlWithKbListSort,
  getKbListSortField,
  getKbListSortLabel,
  getKbListSortPillLabel,
  KB_LIST_SORT_FIELDS,
  toggleKbListSort,
  type KbListSortField,
  type KbListSortMode,
} from "@/lib/kb-list-utils";
import { getKbListSearchEmptyCopy } from "@/lib/kb-empty-copy";
import { cn } from "@/lib/utils";

interface KbListSearchBarProps {
  pathname: string;
  search: string;
  query: string;
  sortMode: KbListSortMode;
  resultCount: number;
}

export function KbListSearchBar({
  pathname,
  search,
  query,
  sortMode,
  resultCount,
}: KbListSearchBarProps) {
  const navigate = useNavigate();

  function handleQueryChange(next: string) {
    navigate(buildUrlWithKbListQuery(pathname, search, next), { replace: true });
  }

  function handleSortClick(field: KbListSortField) {
    const next = toggleKbListSort(sortMode, field);
    navigate(buildUrlWithKbListSort(pathname, search, next), { replace: true });
  }

  return (
    <div className="mb-4 space-y-2.5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <KbSearchInput
          id="kb-list-search"
          value={query}
          placeholder="搜索资料库…"
          onChange={handleQueryChange}
          className="w-full sm:max-w-md"
        />
        <div
          className="flex flex-nowrap items-center gap-1.5 overflow-x-auto pb-1 sm:w-auto"
          role="group"
          aria-label="资料库排序"
        >
          {KB_LIST_SORT_FIELDS.map((field) => {
            const active = getKbListSortField(sortMode) === field;
            const label = getKbListSortPillLabel(field, sortMode);
            return (
              <button
                key={field}
                type="button"
                onClick={() => handleSortClick(field)}
                className={cn(
                  "kb-sort-pill",
                  active ? "kb-sort-pill-active" : "kb-sort-pill-idle",
                )}
                aria-pressed={active}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>
      <p className="text-[0.72rem] text-muted">
        共 {resultCount} 个资料库 · 按{getKbListSortLabel(sortMode)}
      </p>
    </div>
  );
}

interface KbListSearchEmptyPanelProps {
  query: string;
  clearTo: string;
}

export function KbListSearchEmptyPanel({
  query,
  clearTo,
}: KbListSearchEmptyPanelProps) {
  const { title, description } = getKbListSearchEmptyCopy(query);

  return (
    <KbResultEmptyPanel
      title={title}
      description={description}
      live
      action={
        <Button
          asChild
          type="button"
          variant="outline"
          size="sm"
          className="kb-result-empty-clear"
        >
          <Link to={clearTo}>清除搜索</Link>
        </Button>
      }
    />
  );
}
