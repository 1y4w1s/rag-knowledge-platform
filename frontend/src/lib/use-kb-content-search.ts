import { useCallback, useEffect, useState } from "react";

import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";
import {
  fetchSearchDocuments,
  SEARCH_PAGE_SIZE,
  type SearchDocumentItem,
} from "@/lib/search-api";

export function useKbContentSearch(
  kbId: string | undefined,
  query: string,
  enabled: boolean,
) {
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: deptGen,
    getGeneration: getDeptGen,
  } = useDepartment();

  const [items, setItems] = useState<SearchDocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pageCount = Math.max(1, Math.ceil(total / SEARCH_PAGE_SIZE));
  const trimmed = query.trim();

  const loadPage = useCallback(
    async (nextPage: number) => {
      if (!kbId || !enabled || trimmed.length < 1) {
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
          mode: "content",
          kbId,
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
      kbId,
      enabled,
      trimmed,
      workspace,
      departmentId,
      generation,
      deptGen,
      getGeneration,
      getDeptGen,
    ],
  );

  useEffect(() => {
    void loadPage(1);
  }, [loadPage]);

  const goToPage = useCallback(
    (nextPage: number) => {
      void loadPage(nextPage);
    },
    [loadPage],
  );

  return {
    items,
    total,
    page,
    pageCount,
    pageSize: SEARCH_PAGE_SIZE,
    loading,
    error,
    goToPage,
    hasQuery: trimmed.length > 0,
  };
}
