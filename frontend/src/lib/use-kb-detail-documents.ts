import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DOCUMENT_PAGE_SIZE,
  fetchAllDocuments,
  fetchDocumentsPage,
  isDocumentProcessing,
  type Document,
} from "@/lib/document-api";
import {
  buildUrlWithoutListFilters,
  hasActiveListFilters,
  parseDocumentListFilters,
  toDocumentListApiFilters,
} from "@/lib/document-advanced-filter";
import {
  buildUrlWithoutDocumentQuery,
  filterDocumentsByQuery,
  parseDocumentQuery,
  sortDocuments,
  type DocumentSortMode,
} from "@/lib/document-list-utils";
import {
  buildUrlWithoutStatusFilter,
  parseStatusFilter,
} from "@/lib/document-status-filter";

function needsFullDocumentList(
  documentQuery: string,
  sortMode: DocumentSortMode,
): boolean {
  return documentQuery.length > 0 || sortMode !== "uploaded_at_desc";
}

export function useKbDetailDocuments(
  kbId: string | undefined,
  search: string,
  pathname: string,
  sortMode: DocumentSortMode,
) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const loadedKbIdRef = useRef<string | undefined>(undefined);

  const listFilters = useMemo(
    () => parseDocumentListFilters(search),
    [search],
  );
  const apiFilters = useMemo(
    () => toDocumentListApiFilters(listFilters),
    [listFilters],
  );
  const hasListFilters = hasActiveListFilters(listFilters);
  const statusFilter = parseStatusFilter(search);
  const documentQuery = parseDocumentQuery(search);
  const clearFilterTo = buildUrlWithoutStatusFilter(pathname, search);
  const clearListFiltersTo = buildUrlWithoutListFilters(pathname, search);
  const clearSearchTo = buildUrlWithoutDocumentQuery(pathname, search);
  const useFullList = needsFullDocumentList(documentQuery, sortMode);

  const pageCount = Math.max(1, Math.ceil(total / DOCUMENT_PAGE_SIZE));

  const displayDocuments = useMemo(() => {
    const filtered = filterDocumentsByQuery(documents, documentQuery);
    return sortDocuments(filtered, sortMode);
  }, [documents, documentQuery, sortMode]);

  const loadDocumentsPage = useCallback(
    async (id: string, nextPage: number) => {
      const offset = (nextPage - 1) * DOCUMENT_PAGE_SIZE;
      const result = await fetchDocumentsPage(id, {
        limit: DOCUMENT_PAGE_SIZE,
        offset,
        ...apiFilters,
      });
      setDocuments(result.items);
      setTotal(result.total);
      setPage(nextPage);
      return result.items;
    },
    [apiFilters],
  );

  const loadAllDocuments = useCallback(
    async (id: string) => {
      const items = await fetchAllDocuments(id, apiFilters);
      setDocuments(items);
      setTotal(items.length);
      setPage(1);
      return items;
    },
    [apiFilters],
  );

  const loadDocuments = useCallback(
    async (id: string, options?: { page?: number }) => {
      loadedKbIdRef.current = id;
      if (useFullList) {
        return loadAllDocuments(id);
      }
      return loadDocumentsPage(id, options?.page ?? page);
    },
    [useFullList, loadAllDocuments, loadDocumentsPage, page],
  );

  const resetDocuments = useCallback(() => {
    setDocuments([]);
    setTotal(0);
    setPage(1);
    loadedKbIdRef.current = undefined;
  }, []);

  const goToPage = useCallback(
    async (nextPage: number) => {
      if (!kbId || useFullList) return;
      const clamped = Math.min(Math.max(nextPage, 1), pageCount);
      await loadDocumentsPage(kbId, clamped);
    },
    [kbId, useFullList, pageCount, loadDocumentsPage],
  );

  useEffect(() => {
    if (!kbId) return;

    if (loadedKbIdRef.current !== kbId) {
      loadedKbIdRef.current = kbId;
      return;
    }

    if (useFullList) {
      void loadAllDocuments(kbId).catch(() => {
        /* filter/sort/search reload is best-effort */
      });
      return;
    }

    void loadDocumentsPage(kbId, 1).catch(() => {
      /* filter/sort/search reload is best-effort */
    });
  }, [
    kbId,
    search,
    sortMode,
    useFullList,
    loadAllDocuments,
    loadDocumentsPage,
  ]);

  useEffect(() => {
    if (!kbId) return;
    const id = kbId;

    function refreshDocuments() {
      void loadDocuments(id).catch(() => {
        /* tab refocus sync is best-effort */
      });
    }

    window.addEventListener("focus", refreshDocuments);
    return () => window.removeEventListener("focus", refreshDocuments);
  }, [kbId, loadDocuments]);

  useEffect(() => {
    if (!kbId) return;

    const hasProcessing = documents.some((doc) =>
      isDocumentProcessing(doc.status),
    );
    if (!hasProcessing) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    if (pollRef.current) return;

    pollRef.current = setInterval(() => {
      void loadDocuments(kbId).catch(() => {
        /* polling errors are non-fatal */
      });
    }, 2500);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documents, kbId, loadDocuments]);

  return {
    documents,
    total,
    page,
    pageCount,
    useFullList,
    setDocuments,
    resetDocuments,
    loadDocuments,
    goToPage,
    statusFilter,
    hasListFilters,
    listFilters,
    documentQuery,
    clearFilterTo,
    clearListFiltersTo,
    clearSearchTo,
    displayDocuments,
  };
}
