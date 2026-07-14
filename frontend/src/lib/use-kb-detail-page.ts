import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth-context";
import type { DocumentSortMode } from "@/lib/document-list-utils";
import {
  fetchKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";
import { buildKbDetailBreadcrumb } from "@/lib/breadcrumb-links";
import { canUseTeamBusiness, canWriteKnowledgeBase, isTeamMemberReadOnly } from "@/lib/org-permissions";
import { persistRecentKbId } from "@/lib/use-sidebar-chat-kb-id";
import { useKbDetailDocuments } from "@/lib/use-kb-detail-documents";
import { useKbDocumentActions } from "@/lib/use-kb-document-actions";
import { useWorkspace } from "@/lib/workspace-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";

export function useKbDetailPage(kbId: string | undefined) {
  const { pathname, search } = useLocation();
  const { user } = useAuth();
  const { workspace } = useWorkspace();
  const { setOverride } = useShellBreadcrumb();
  const { toast, show: showToast, dismiss: dismissToast } = useToast();

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [sortMode, setSortMode] = useState<DocumentSortMode>("uploaded_at_desc");

  const {
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
  } = useKbDetailDocuments(kbId, search, pathname, sortMode);

  const actions = useKbDocumentActions(
    kbId,
    documents,
    setDocuments,
    loadDocuments,
    showToast,
  );

  const uploadAllowed = canWriteKnowledgeBase(user, workspace);
  const chatAllowed = canUseTeamBusiness(user, workspace);
  const isMemberReadOnly = isTeamMemberReadOnly(user, workspace);

  const clearInlineErrors = actions.clearInlineErrors;

  const loadPage = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    setError(null);
    clearInlineErrors();
    setKb(null);
    resetDocuments();
    try {
      const kbData = await fetchKnowledgeBase(kbId);
      setKb(kbData);
      persistRecentKbId(kbId, workspace);
      document.title = `知岸 · ${kbData.name}`;
      setOverride(buildKbDetailBreadcrumb(kbData.name));
      await loadDocuments(kbId, { page: 1 });
    } catch (err) {
      setKb(null);
      resetDocuments();
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [
    kbId,
    workspace,
    loadDocuments,
    setOverride,
    clearInlineErrors,
    resetDocuments,
  ]);

  useEffect(() => {
    void loadPage();
    return () => {
      setOverride(null);
      document.title = "知岸";
    };
  }, [loadPage, setOverride]);

  const handleKbUpdated = useCallback(
    (updated: KnowledgeBase) => {
      setKb(updated);
      document.title = `知岸 · ${updated.name}`;
      setOverride(buildKbDetailBreadcrumb(updated.name));
    },
    [setOverride],
  );

  const notifyChatBlocked = useCallback(() => {
    showToast("分配部门后即可开始对话");
  }, [showToast]);

  return {
    kbId,
    pathname,
    search,
    kb,
    loading,
    error,
    editOpen,
    setEditOpen,
    sortMode,
    setSortMode,
    uploadAllowed,
    chatAllowed,
    isMemberReadOnly,
    documents,
    total,
    page,
    pageCount,
    useFullList,
    goToPage,
    statusFilter,
    hasListFilters,
    listFilters,
    documentQuery,
    clearFilterTo,
    clearListFiltersTo,
    clearSearchTo,
    displayDocuments,
    loadPage,
    handleKbUpdated,
    notifyChatBlocked,
    toast,
    showToast,
    dismissToast,
    ...actions,
  };
}
