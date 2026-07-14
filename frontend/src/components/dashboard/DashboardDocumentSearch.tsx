import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";

import { DocumentStatusBadge } from "@/components/knowledge-bases/DocumentStatusBadge";
import { KbSearchInput } from "@/components/knowledge-bases/KbSearchInput";
import { SearchModeTabs } from "@/components/dashboard/SearchModeTabs";
import { SearchSnippet } from "@/components/dashboard/SearchSnippet";
import {
  fetchSearchDocuments,
  type SearchDocumentItem,
  type SearchMode,
} from "@/lib/search-api";
import type { ScopeFetchOptions } from "@/lib/scope-fetch";

const DEBOUNCE_MS = 300;

interface DashboardDocumentSearchProps
  extends Pick<
    ScopeFetchOptions,
    | "expectedGen"
    | "getCurrentGeneration"
    | "expectedDepartmentGen"
    | "getCurrentDepartmentGeneration"
    | "workspace"
    | "departmentId"
  > {}

export function DashboardDocumentSearch({
  expectedGen,
  getCurrentGeneration,
  expectedDepartmentGen,
  getCurrentDepartmentGeneration,
  workspace,
  departmentId,
}: DashboardDocumentSearchProps) {
  const [mode, setMode] = useState<SearchMode>("filename");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchDocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = useCallback(
    async (needle: string, searchMode: SearchMode) => {
      const trimmed = needle.trim();
      if (trimmed.length < 1) {
        setItems([]);
        setTotal(0);
        setError(null);
        setHasSearched(false);
        setLoading(false);
        return;
      }

      const requestGen = expectedGen;
      const requestDeptGen = expectedDepartmentGen ?? 0;
      setLoading(true);
      setError(null);
      setHasSearched(true);

      try {
        const data = await fetchSearchDocuments(trimmed, {
          expectedGen: requestGen,
          getCurrentGeneration,
          expectedDepartmentGen: requestDeptGen,
          getCurrentDepartmentGeneration,
          workspace,
          departmentId,
        }, searchMode);
        if (data === null) return;
        if (getCurrentGeneration() !== requestGen) return;
        if (getCurrentDepartmentGeneration?.() !== requestDeptGen) return;
        setItems(data.items);
        setTotal(data.total);
      } catch (err) {
        if (getCurrentGeneration() !== requestGen) return;
        if (getCurrentDepartmentGeneration?.() !== requestDeptGen) return;
        setItems([]);
        setTotal(0);
        setError(err instanceof Error ? err.message : "搜索失败");
      } finally {
        if (
          getCurrentGeneration() === requestGen &&
          getCurrentDepartmentGeneration?.() === requestDeptGen
        ) {
          setLoading(false);
        }
      }
    },
    [
      expectedGen,
      getCurrentGeneration,
      expectedDepartmentGen,
      getCurrentDepartmentGeneration,
      workspace,
      departmentId,
    ],
  );

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      void runSearch(query, mode);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, mode, runSearch]);

  useEffect(() => {
    setQuery("");
    setItems([]);
    setTotal(0);
    setError(null);
    setHasSearched(false);
    setLoading(false);
  }, [workspace, expectedGen, expectedDepartmentGen]);

  const placeholder =
    mode === "content"
      ? "搜索文档正文，跨所有资料库…"
      : "搜索文件名，跨所有资料库…";

  const emptyHint =
    mode === "content"
      ? "未找到包含该关键词的文档正文。请确认文档已上传并完成整理。"
      : "未找到匹配的文件。可先创建资料库并上传文档。";

  return (
    <section
      className="rounded-xl border border-border bg-white/80 p-4 shadow-sm md:p-5"
      aria-labelledby="dashboard-doc-search-title"
    >
      <div className="mb-3">
        <h2
          id="dashboard-doc-search-title"
          className="font-serif text-base font-semibold tracking-[0.02em] text-foreground"
        >
          找文档
        </h2>
        <p className="mt-1 text-sm text-[var(--mut)]">
          在当前空间的所有资料库中查找文档；可按文件名或正文关键词搜索。
        </p>
      </div>

      <SearchModeTabs active={mode} onChange={setMode} />

      <KbSearchInput
        id="dashboard-doc-search"
        value={query}
        placeholder={placeholder}
        onChange={setQuery}
        className="max-w-none"
      />

      {loading && (
        <p className="mt-3 text-sm text-[var(--mut)]" role="status" aria-live="polite">
          正在搜索…
        </p>
      )}

      {error && !loading && (
        <p className="mt-3 text-sm text-[var(--err)]" role="alert" aria-live="assertive">
          {error}
        </p>
      )}

      {!loading && !error && hasSearched && query.trim().length >= 1 && (
        <div className="mt-3" aria-live="polite" aria-atomic="true">
          {items.length === 0 ? (
            <p className="text-sm text-[var(--mut)]">
              {emptyHint}
            </p>
          ) : (
            <>
              <p className="mb-2 text-xs text-[var(--mut)]">
                共 {total} 个结果
                {total > items.length ? `（显示前 ${items.length} 条）` : ""}
              </p>
              <ul className="divide-y divide-border rounded-lg border border-border bg-white">
                {items.map((item) => (
                  <li key={item.doc_id}>
                    <Link
                      to={`/knowledge-bases/${item.kb_id}?q=${encodeURIComponent(item.filename)}`}
                      className="group flex items-start gap-3 px-3 py-3 text-sm transition-colors hover:bg-[rgba(166,139,107,0.06)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(166,139,107,0.35)]"
                    >
                      <FileText
                        className="mt-0.5 h-[18px] w-[18px] shrink-0 text-[#A68B6B]"
                        strokeWidth={1.5}
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span className="min-w-0 font-medium text-foreground">
                            {item.filename}
                          </span>
                          <span className="text-xs text-[var(--mut)]">
                            {item.kb_name}
                          </span>
                          <DocumentStatusBadge status={item.status} />
                        </div>
                        {mode === "content" && item.snippet && (
                          <p className="mt-1.5">
                            {item.page_number != null && (
                              <span className="mr-2 text-xs text-[var(--mut)]">
                                第 {item.page_number} 页
                              </span>
                            )}
                            <SearchSnippet html={item.snippet} />
                          </p>
                        )}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
