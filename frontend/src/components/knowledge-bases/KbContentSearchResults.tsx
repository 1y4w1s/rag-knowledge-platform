import { Link } from "react-router-dom";

import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import {
  KbResultEmptyPanel,
  type SearchSuggestionItem,
} from "@/components/knowledge-bases/KbResultEmptyPanel";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { SearchSnippet } from "@/lib/search-snippet";
import { buildUrlWithDocumentQuery } from "@/lib/document-list-utils";
import { DEFAULT_SEARCH_SUGGESTIONS } from "@/lib/kb-empty-copy";
import type { SearchDocumentItem } from "@/lib/search-api";

type KbContentSearchResultsProps = {
  kbId: string;
  query: string;
  items: SearchDocumentItem[];
  total: number;
  page: number;
  pageCount: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  hasQuery: boolean;
  clearTo: string;
  pathname: string;
  search: string;
  onPageChange: (page: number) => void;
  onRetry: () => void;
};

export function KbContentSearchResults({
  kbId,
  query,
  items,
  total,
  page,
  pageCount,
  pageSize,
  loading,
  error,
  hasQuery,
  clearTo,
  pathname,
  search,
  onPageChange,
  onRetry,
}: KbContentSearchResultsProps) {
  if (!hasQuery) {
    return (
      <div className="flex items-start gap-2 py-6 text-sm text-[var(--mut)]">
        <span className="inline-flex shrink-0 items-center gap-1 rounded-[6px] border border-[var(--line2)] bg-[var(--surf)] px-2 py-0.5 text-xs font-medium text-foreground">
          正文搜索
        </span>
        <span>
          输入关键词，在本库正文中查找（多关键词用空格分隔，不经过对话）。
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <AlertBanner
        action={
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            重试
          </Button>
        }
      >
        {error}
      </AlertBanner>
    );
  }

  if (loading) {
    return (
      <div
        className="animate-pulse rounded-[10px] border border-[var(--line2)] bg-[var(--surf)]"
        aria-label="搜索正文中"
      >
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex flex-col gap-2 border-b border-[var(--line2)] px-4 py-3 last:border-b-0"
          >
            <div className="flex items-baseline justify-between gap-2">
              <div className="h-4 w-3/5 rounded bg-[var(--surf2)]" />
              <div className="h-3 w-14 rounded bg-[var(--surf2)]" />
            </div>
            <div className="space-y-1.5">
              <div className="h-3 w-full rounded bg-[var(--surf2)]" />
              <div className="h-3 w-4/5 rounded bg-[var(--surf2)]" />
              <div className="h-3 w-1/2 rounded bg-[var(--surf2)]" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (total === 0) {
    const suggestions: SearchSuggestionItem[] = DEFAULT_SEARCH_SUGGESTIONS.map(
      (kw) => ({
        label: kw,
        to: buildUrlWithDocumentQuery(pathname, search, kw),
      }),
    );

    return (
      <KbResultEmptyPanel
        title="本库正文未找到匹配"
        description={`没有找到正文包含「${query}」的文档。试试其他关键词，或切换到文件名搜索。`}
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

  return (
    <>
      <ul className="divide-y divide-[var(--line2)] rounded-[10px] border border-[var(--line2)] bg-[var(--surf)]">
        {items.map((item) => (
          <li key={item.doc_id}>
            <Link
              to={`/knowledge-bases/${kbId}/documents/${item.doc_id}`}
              className="block px-4 py-3 transition-colors hover:bg-[var(--line)]/40"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-foreground">
                  {item.filename}
                </span>
                {item.page_number != null ? (
                  <span className="text-xs text-[var(--mut)]">
                    第 {item.page_number} 页
                  </span>
                ) : null}
              </div>
              {item.snippet ? (
                <p className="mt-1.5 text-xs leading-relaxed text-[var(--mut)]">
                  <SearchSnippet snippet={item.snippet} />
                </p>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
      <DocumentListPagination
        page={page}
        pageCount={pageCount}
        total={total}
        pageSize={pageSize}
        onPageChange={onPageChange}
        itemUnit="篇"
      />
    </>
  );
}
