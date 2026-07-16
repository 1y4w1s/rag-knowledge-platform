import { useRef, useState, type ChangeEvent } from "react";

import { DocumentListFiltersEmptyPanel } from "@/components/knowledge-bases/DocumentListFiltersEmptyPanel";
import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import {
  DocumentFilterEmptyPanel,
} from "@/components/knowledge-bases/DocumentStatusFilterBar";
import {
  DocumentListToolbar,
  DocumentSearchEmptyPanel,
} from "@/components/knowledge-bases/DocumentListToolbar";
import { DocumentTable } from "@/components/knowledge-bases/DocumentTable";
import { EmptyStateV44, KBDETAIL_SCENE } from "@/components/ui/EmptyState";
import { MemberReadOnlyHint } from "@/components/knowledge-bases/MemberReadOnlyHint";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { TrashDialog } from "@/components/knowledge-bases/TrashDialog";
import { useAuth } from "@/lib/auth-context";
import { updateDocumentVisibility, type Document, DOCUMENT_PAGE_SIZE } from "@/lib/document-api";
import type { DocumentListFilters } from "@/lib/document-advanced-filter";
import type { DocumentSortMode } from "@/lib/document-list-utils";
import type { DocumentStatusFilter } from "@/lib/document-status-filter";

type KnowledgeBaseDetailDocumentSectionProps = {
  kbId: string;
  pathname: string;
  search: string;
  displayDocuments: Document[];
  total: number;
  page: number;
  pageCount: number;
  useFullList: boolean;
  onPageChange: (page: number) => void;
  statusFilter: DocumentStatusFilter | null;
  hasListFilters: boolean;
  listFilters: DocumentListFilters;
  documentQuery: string;
  clearFilterTo: string;
  clearListFiltersTo: string;
  clearSearchTo: string;
  sortMode: DocumentSortMode;
  onSortChange: (mode: DocumentSortMode) => void;
  uploadAllowed: boolean;
  isMemberReadOnly: boolean;
  uploading: boolean;
  inlineError: string | null;
  deletingDocId: string | null;
  onClearInlineErrors: () => void;
  onRefresh: () => void;
  onUpload: (files: File[]) => void;
  onRequestDelete: (doc: Document) => void;
  onRetry: (docId: string) => Promise<void>;
  onVisibilityToast: (message: string) => void;
};

export function KnowledgeBaseDetailDocumentSection({
  kbId,
  pathname,
  search,
  displayDocuments,
  total,
  page,
  pageCount,
  useFullList,
  onPageChange,
  statusFilter,
  hasListFilters,
  listFilters,
  documentQuery,
  clearFilterTo,
  clearListFiltersTo,
  clearSearchTo,
  sortMode,
  onSortChange,
  uploadAllowed,
  inlineError,
  deletingDocId,
  onClearInlineErrors,
  onRefresh,
  onUpload,
  onRequestDelete,
  onRetry,
  onVisibilityToast,
}: KnowledgeBaseDetailDocumentSectionProps) {
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const { isOrgAdmin, user } = useAuth();
  const canChangeVisibility = isOrgAdmin || user?.is_owner === true;
  const [trashOpen, setTrashOpen] = useState(false);
  const [pendingVisibilityId, setPendingVisibilityId] = useState<string | null>(null);

  async function handleVisibilityChange(docId: string, visibility: "everyone" | "admin_only") {
    setPendingVisibilityId(docId);
    try {
      await updateDocumentVisibility(kbId, docId, visibility);
      onVisibilityToast(
        visibility === "admin_only" ? "已改为仅管理员可见" : "已改为全员可见",
      );
      onRefresh();
    } catch (err) {
      onVisibilityToast(
        err instanceof Error ? err.message : "可见性修改失败",
      );
    } finally {
      setPendingVisibilityId(null);
    }
  }
  function handleUploadInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length > 0) onUpload(files);
  }
  return (
    <>
      {inlineError && (
        <AlertBanner
          className="mb-4"
          onDismiss={onClearInlineErrors}
          action={
            <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
              刷新列表
            </Button>
          }
        >
          {inlineError}
        </AlertBanner>
      )}

      {!uploadAllowed && <MemberReadOnlyHint />}

      {total === 0 && !statusFilter && !hasListFilters ? (
        <>
          <EmptyStateV44
            scene={{
              ...KBDETAIL_SCENE,
              ctaPrimary: {
                ...KBDETAIL_SCENE.ctaPrimary,
                onClick: uploadAllowed
                  ? () => uploadInputRef.current?.click()
                  : undefined,
              },
              ctaSecondary: {
                ...KBDETAIL_SCENE.ctaSecondary,
                onClick: uploadAllowed
                  ? () => uploadInputRef.current?.click()
                  : undefined,
              },
            }}
          />
          <input
            ref={uploadInputRef}
            type="file"
            accept=".pdf,.txt,.md,.docx,.png,.jpg,.jpeg"
            multiple
            className="hidden"
            onChange={handleUploadInputChange}
          />
        </>
      ) : (
        <>
          <SectionTitle
            label="文档"
            en="DOCUMENTS"
            count={total}
            trailing={
              uploadAllowed ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setTrashOpen(true)}
                >
                  回收站
                </Button>
              ) : undefined
            }
          />
          <DocumentListToolbar
            pathname={pathname}
            search={search}
            query={documentQuery}
            statusFilter={statusFilter}
            sortMode={sortMode}
            onSortChange={onSortChange}
          />

          {statusFilter && displayDocuments.length === 0 ? (
            <DocumentFilterEmptyPanel
              filter={statusFilter}
              clearTo={clearFilterTo}
            />
          ) : hasListFilters && displayDocuments.length === 0 ? (
            <DocumentListFiltersEmptyPanel
              filters={listFilters}
              clearTo={clearListFiltersTo}
            />
          ) : documentQuery && displayDocuments.length === 0 ? (
            <DocumentSearchEmptyPanel
              query={documentQuery}
              clearTo={clearSearchTo}
            />
          ) : (
            <>
              <DocumentTable
                kbId={kbId}
                documents={displayDocuments}
                canManage={uploadAllowed}
                canChangeVisibility={canChangeVisibility}
                pendingVisibilityId={pendingVisibilityId}
                deletingDocId={deletingDocId}
                onRequestDelete={onRequestDelete}
                onRetry={onRetry}
                onVisibilityChange={handleVisibilityChange}
              />
              {!useFullList && (
                <DocumentListPagination
                  page={page}
                  pageCount={pageCount}
                  total={total}
                  pageSize={DOCUMENT_PAGE_SIZE}
                  onPageChange={onPageChange}
                />
              )}
            </>
          )}
        </>
      )}

      <TrashDialog
        kbId={kbId}
        open={trashOpen}
        onOpenChange={setTrashOpen}
        onRefresh={onRefresh}
      />
    </>
  );
}
