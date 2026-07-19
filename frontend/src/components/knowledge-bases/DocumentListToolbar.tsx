import { Link, useNavigate } from "react-router-dom";

import { DocumentAdvancedFilter } from "@/components/knowledge-bases/DocumentAdvancedFilter";
import { DocumentStatusFilterBar } from "@/components/knowledge-bases/DocumentStatusFilterBar";
import { KbResultEmptyPanel } from "@/components/knowledge-bases/KbResultEmptyPanel";
import { KbSearchInput } from "@/components/knowledge-bases/KbSearchInput";
import { Button } from "@/components/ui/button";
import {
  buildUrlWithoutStatusFilter,
  type DocumentStatusFilter,
} from "@/lib/document-status-filter";
import {
  buildUrlWithDocumentQuery,
  type DocumentSortMode,
} from "@/lib/document-list-utils";
import { getDocumentSearchEmptyCopy } from "@/lib/kb-empty-copy";
import { cn } from "@/lib/utils";

interface DocumentListToolbarProps {
  pathname: string;
  search: string;
  query: string;
  statusFilter: DocumentStatusFilter | null;
  sortMode: DocumentSortMode;
  onSortChange: (mode: DocumentSortMode) => void;
}

const SORT_OPTIONS: { mode: DocumentSortMode; label: string }[] = [
  { mode: "uploaded_at_desc", label: "上传时间 ↓" },
  { mode: "filename_asc", label: "文件名 A→Z" },
];

export function DocumentListToolbar({
  pathname,
  search,
  query,
  statusFilter,
  sortMode,
  onSortChange,
}: DocumentListToolbarProps) {
  const navigate = useNavigate();
  const clearStatusTo = buildUrlWithoutStatusFilter(pathname, search);

  function handleQueryChange(next: string) {
    navigate(buildUrlWithDocumentQuery(pathname, search, next), {
      replace: true,
    });
  }

  return (
    <div className="mb-4 space-y-2.5">
      {statusFilter && (
        <DocumentStatusFilterBar filter={statusFilter} clearTo={clearStatusTo} />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <KbSearchInput
          id="document-list-search"
          value={query}
          placeholder="搜索文件名…"
          onChange={handleQueryChange}
          className="max-w-[360px]"
        />
        <DocumentAdvancedFilter pathname={pathname} search={search} />
        <div
          className="flex flex-wrap items-center gap-1.5"
          role="group"
          aria-label="文档排序"
        >
          {SORT_OPTIONS.map(({ mode, label }) => {
            const active = sortMode === mode;
            return (
              <button
                key={mode}
                type="button"
                onClick={() => onSortChange(mode)}
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
    </div>
  );
}

interface DocumentSearchEmptyPanelProps {
  query: string;
  clearTo: string;
}

export function DocumentSearchEmptyPanel({
  query,
  clearTo,
}: DocumentSearchEmptyPanelProps) {
  const { title, description } = getDocumentSearchEmptyCopy(query);

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
