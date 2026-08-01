import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import { KbSearchInput } from "@/components/knowledge-bases/KbSearchInput";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { useDepartment } from "@/lib/department-context";
import { SearchSnippet } from "@/lib/search-snippet";
import {
  fetchSearchDocuments,
  SEARCH_PAGE_SIZE,
  type SearchDocumentItem,
  type SearchMode,
} from "@/lib/search-api";
import { useWorkspace } from "@/lib/workspace-context";
import { DEFAULT_SEARCH_SUGGESTIONS } from "@/lib/kb-empty-copy";
import { cn } from "@/lib/utils";

const MODE_OPTIONS: { mode: SearchMode; label: string }[] = [
  { mode: "filename", label: "文件名" },
  { mode: "content", label: "正文" },
];

export function FindDocumentsPanel() {
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: deptGen,
    getGeneration: getDeptGen,
  } = useDepartment();

  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [mode, setMode] = useState<SearchMode>("filename");
  const [items, setItems] = useState<SearchDocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / SEARCH_PAGE_SIZE));

  const runSearch = useCallback(
    async (q: string, nextMode: SearchMode, nextPage: number) => {
      const trimmed = q.trim();
      if (trimmed.length < 1) {
        setItems([]);
        setTotal(0);
        setPage(1);
        setError(null);
        setLoading(false);
        return;
      }

      const eg = generation;
      const ed = deptGen;
      setLoading(true);
      setError(null);
      try {
        const offset = (nextPage - 1) * SEARCH_PAGE_SIZE;
        const data = await fetchSearchDocuments({
          q: trimmed,
          mode: nextMode,
          limit: SEARCH_PAGE_SIZE,
          offset,
          scope: {
            workspace,
            departmentId: workspace === "personal" ? null : departmentId,
            expectedGen: eg,
            getCurrentGeneration: getGeneration,
            expectedDepartmentGen: ed,
            getCurrentDepartmentGeneration: getDeptGen,
          },
        });
        if (
          data === null ||
          getGeneration() !== eg ||
          getDeptGen() !== ed
        ) {
          return;
        }
        setItems(data.items);
        setTotal(data.total);
        setPage(nextPage);
      } catch (err) {
        if (getGeneration() !== eg || getDeptGen() !== ed) return;
        setItems([]);
        setTotal(0);
        setError(err instanceof Error ? err.message : "搜索失败");
      } finally {
        if (getGeneration() === eg && getDeptGen() === ed) {
          setLoading(false);
        }
      }
    },
    [
      workspace,
      departmentId,
      generation,
      deptGen,
      getGeneration,
      getDeptGen,
    ],
  );

  useEffect(() => {
    if (!submitted) return;
    void runSearch(submitted, mode, 1);
  }, [submitted, mode, workspace, departmentId, runSearch]);

  function handleSubmit(next: string) {
    const trimmed = next.trim();
    setDraft(next);
    setSubmitted(trimmed);
    if (!trimmed) {
      setItems([]);
      setTotal(0);
      setPage(1);
      setError(null);
    }
  }

  function handleModeChange(next: SearchMode) {
    setMode(next);
  }

  return (
    <section aria-label="找文档" className="mt-7">
      <SectionTitle label="找文档" en="FIND" tone="quiet" />
      <div className="dash-panel space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <KbSearchInput
            id="dashboard-find-documents"
            value={draft}
            placeholder={
              mode === "content" ? "搜索文档正文（多词空格）…" : "搜索文件名…"
            }
            onChange={handleSubmit}
            className="max-w-[360px]"
          />
          <div
            className="flex flex-wrap items-center gap-1.5"
            role="group"
            aria-label="搜索方式"
          >
            {MODE_OPTIONS.map(({ mode: m, label }) => (
              <button
                key={m}
                type="button"
                onClick={() => handleModeChange(m)}
                className={cn(
                  "kb-sort-pill",
                  mode === m ? "kb-sort-pill-active" : "kb-sort-pill-idle",
                )}
                aria-pressed={mode === m}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {!submitted ? (
          <p className="text-sm text-[var(--mut)]">
            按文件名或正文查找当前空间可见文档，不经过对话。
          </p>
        ) : null}

        {error ? (
          <AlertBanner
            action={
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void runSearch(submitted, mode, page)}
              >
                重试
              </Button>
            }
          >
            {error}
          </AlertBanner>
        ) : null}

        {loading ? (
          <p className="py-4 text-sm text-[var(--mut)]">搜索中…</p>
        ) : null}

        {!loading && submitted && !error && total === 0 ? (
          <div className="py-4 text-center">
            <p className="text-sm text-[var(--mut)]">
              没有匹配「{submitted}」的文档。试试其他关键词。
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {DEFAULT_SEARCH_SUGGESTIONS.map((kw) => (
                <button
                  key={kw}
                  type="button"
                  className="kb-suggestion-tag"
                  onClick={() => handleSubmit(kw)}
                >
                  {kw}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {!loading && items.length > 0 ? (
          <>
            <ul className="flex flex-col gap-1.5">
              {items.map((item) => (
                <li key={`${item.doc_id}-${item.kb_id}`}>
                  <Link
                    to={
                      mode === "content"
                        ? `/knowledge-bases/${item.kb_id}?q=${encodeURIComponent(submitted)}&search_mode=content`
                        : `/knowledge-bases/${item.kb_id}?q=${encodeURIComponent(submitted)}`
                    }
                    className="dash-feed-row block rounded-[10px] px-3 py-2.5 transition-colors"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-medium text-foreground">
                        {item.filename}
                      </span>
                      <span className="text-xs text-[var(--mut)]">
                        {item.kb_name}
                      </span>
                    </div>
                    {mode === "content" && item.snippet ? (
                      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-[var(--mut)]">
                        <SearchSnippet snippet={item.snippet} />
                        {item.page_number != null
                          ? ` · 第 ${item.page_number} 页`
                          : null}
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
              pageSize={SEARCH_PAGE_SIZE}
              onPageChange={(next) => {
                void runSearch(submitted, mode, next);
              }}
              itemUnit="篇"
            />
          </>
        ) : null}
      </div>
    </section>
  );
}
