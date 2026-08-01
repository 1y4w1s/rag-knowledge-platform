import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DocumentAdvancedFilter } from "@/components/knowledge-bases/DocumentAdvancedFilter";
import { DocumentStatusFilterBar } from "@/components/knowledge-bases/DocumentStatusFilterBar";
import { KbResultEmptyPanel, type SearchSuggestionItem } from "@/components/knowledge-bases/KbResultEmptyPanel";
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
import { buildUrlWithDocumentSearchMode } from "@/lib/document-search-mode";
import { getDocumentSearchEmptyCopy, DEFAULT_SEARCH_SUGGESTIONS } from "@/lib/kb-empty-copy";
import type { SearchMode } from "@/lib/search-api";
import { cn } from "@/lib/utils";

interface DocumentListToolbarProps {
  pathname: string;
  search: string;
  query: string;
  searchMode: SearchMode;
  statusFilter: DocumentStatusFilter | null;
  sortMode: DocumentSortMode;
  onSortChange: (mode: DocumentSortMode) => void;
}

const SORT_OPTIONS: { mode: DocumentSortMode; label: string }[] = [
  { mode: "uploaded_at_desc", label: "上传时间 ↓" },
  { mode: "filename_asc", label: "文件名 A→Z" },
];

const SEARCH_MODE_OPTIONS: { mode: SearchMode; label: string }[] = [
  { mode: "filename", label: "文件名" },
  { mode: "content", label: "正文" },
];

export function DocumentListToolbar({
  pathname,
  search,
  query,
  searchMode,
  statusFilter,
  sortMode,
  onSortChange,
}: DocumentListToolbarProps) {
  const navigate = useNavigate();
  const clearStatusTo = buildUrlWithoutStatusFilter(pathname, search);
  const isContent = searchMode === "content";

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 捕获最新 props 引用，防止防抖闭包读到陈旧 pathname/search
  const latestRef = useRef({ pathname, search, query });
  latestRef.current = { pathname, search, query };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function handleQueryChange(next: string) {
    const { pathname, search, query } = latestRef.current;
    const url = buildUrlWithDocumentQuery(pathname, search, next);

    // 值与 URL 一致→跳过（防止失同步）
    if (next.trim() === query.trim()) return;

    // 清空→清除 pending timer 后立即导航（防止旧 timer 恢复旧查询）
    if (!next) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      navigate(url, { replace: true });
      return;
    }

    // 正常输入→300ms 防抖
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const { pathname, search } = latestRef.current;
      navigate(buildUrlWithDocumentQuery(pathname, search, next), {
        replace: true,
      });
    }, 300);
  }

  function handleModeChange(mode: SearchMode) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const { pathname, search } = latestRef.current;
    navigate(buildUrlWithDocumentSearchMode(pathname, search, mode), {
      replace: true,
    });
  }

  return (
    <div className="mb-4 space-y-2.5">
      {!isContent && statusFilter ? (
        <DocumentStatusFilterBar filter={statusFilter} clearTo={clearStatusTo} />
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <div
          className="flex flex-wrap items-center gap-1.5"
          role="group"
          aria-label="搜索方式"
        >
          {SEARCH_MODE_OPTIONS.map(({ mode, label }) => (
            <button
              key={mode}
              type="button"
              onClick={() => handleModeChange(mode)}
              className={cn(
                "kb-sort-pill",
                searchMode === mode
                  ? "kb-sort-pill-active"
                  : "kb-sort-pill-idle",
              )}
              aria-pressed={searchMode === mode}
            >
              {label}
            </button>
          ))}
        </div>
        <KbSearchInput
          id="document-list-search"
          value={query}
          placeholder={isContent ? "搜索正文（多词空格）…" : "搜索文件名…"}
          onChange={handleQueryChange}
          className="max-w-[360px]"
        />
        {!isContent ? (
          <>
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
          </>
        ) : null}
      </div>
    </div>
  );
}

interface DocumentSearchEmptyPanelProps {
  query: string;
  clearTo: string;
  pathname?: string;
  search?: string;
}

export function DocumentSearchEmptyPanel({
  query,
  clearTo,
  pathname,
  search,
}: DocumentSearchEmptyPanelProps) {
  const { title, description } = getDocumentSearchEmptyCopy(query);

  const suggestions: SearchSuggestionItem[] | undefined =
    pathname && search
      ? DEFAULT_SEARCH_SUGGESTIONS.map((kw) => ({
          label: kw,
          to: buildUrlWithDocumentQuery(pathname, search, kw),
        }))
      : undefined;

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
      suggestions={suggestions}
    />
  );
}
