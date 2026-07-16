import { useEffect, useState } from "react";

import { useParams } from "react-router-dom";



import { DeleteDocumentDialog } from "@/components/knowledge-bases/DeleteDocumentDialog";

import { EditKnowledgeBaseDialog } from "@/components/knowledge-bases/EditKnowledgeBaseDialog";

import { KnowledgeBaseDetailDocumentSection } from "@/components/knowledge-bases/KnowledgeBaseDetailDocumentSection";

import { KnowledgeBaseGrantsPanel } from "@/components/knowledge-bases/KnowledgeBaseGrantsPanel";

import { KnowledgeBaseDetailHeader } from "@/components/knowledge-bases/KnowledgeBaseDetailHeader";

import { KnowledgeBaseDetailSkeleton } from "@/components/knowledge-bases/KnowledgeBaseDetailSkeleton";

import { AlertBanner } from "@/components/ui/AlertBanner";

import { Button } from "@/components/ui/button";

import { Toast } from "@/components/ui/Toast";

import { useAuth } from "@/lib/auth-context";

import { isCompanyAdmin } from "@/lib/department-align";

import { canManageKbGrants } from "@/lib/kb-grant-permissions";

import { fetchOrgUnits, type OrgUnit } from "@/lib/org-units-api";

import { useKbDetailPage } from "@/lib/use-kb-detail-page";

import { useWorkspace } from "@/lib/workspace-context";



export function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { workspace } = useWorkspace();
  const page = useKbDetailPage(id);
  const [grantUnits, setGrantUnits] = useState<OrgUnit[] | null>(null);

  useEffect(() => {
    document.title = "睿阁 · 资料库详情";
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      meta.setAttribute(
        "content",
        "查看知识库详情、管理文档与共享权限。",
      );
    }
  }, []);

  useEffect(() => {
    if (page.kb?.name) {
      document.title = `睿阁 · ${page.kb.name}`;
      const meta = document.querySelector('meta[name="description"]');
      if (meta) {
        meta.setAttribute(
          "content",
          `管理「${page.kb.name}」文档与入库状态，支持上传、检索与共享权限。`,
        );
      }
    }
  }, [page.kb?.name]);



  useEffect(() => {

    if (!user || workspace === "personal" || user.account_type !== "enterprise") {

      setGrantUnits(null);

      return;

    }

    if (isCompanyAdmin(user)) {

      setGrantUnits([]);

      return;

    }

    if ((user.unit_admin_unit_ids?.length ?? 0) === 0) {

      setGrantUnits(null);

      return;

    }



    let cancelled = false;

    void fetchOrgUnits()

      .then((units) => {

        if (!cancelled) setGrantUnits(Array.isArray(units) ? units : []);

      })

      .catch(() => {

        if (!cancelled) setGrantUnits([]);

      });

    return () => {

      cancelled = true;

    };

  }, [user, workspace]);



  if (!id) {

    return (

      <AlertBanner className="rounded-lg">无效的资料库地址</AlertBanner>

    );

  }



  if (page.loading) {

    return <KnowledgeBaseDetailSkeleton />;

  }



  if (page.error || !page.kb) {

    return (

      <AlertBanner

        action={

          <Button type="button" variant="outline" size="sm" onClick={page.loadPage}>

            重试

          </Button>

        }

      >

        {page.error ?? "资料库不存在"}

      </AlertBanner>

    );

  }



  const inlineError = page.uploadError ?? page.actionError;

  const showGrantsPanel =

    Boolean(user) &&

    canManageKbGrants(user, page.kb, workspace, grantUnits);



  return (
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
      <KnowledgeBaseDetailHeader

        kb={page.kb}

        kbId={id}

        uploadAllowed={page.uploadAllowed}

        chatAllowed={page.chatAllowed}

        uploading={page.uploading}

        onEdit={() => page.setEditOpen(true)}

        onUpload={(files) => void page.handleUpload(files)}

        onMemberWriteBlocked={page.notifyMemberWriteBlocked}

        onChatBlocked={page.notifyChatBlocked}

      />



      {showGrantsPanel && user && (

        <KnowledgeBaseGrantsPanel

          kb={page.kb}

          kbId={id}

          user={user}

          onToast={page.showToast}

        />

      )}



      <KnowledgeBaseDetailDocumentSection

        kbId={id}

        pathname={page.pathname}

        search={page.search}

        displayDocuments={page.displayDocuments}

        total={page.total}

        page={page.page}

        pageCount={page.pageCount}

        useFullList={page.useFullList}

        onPageChange={(nextPage) => {

          void page.goToPage(nextPage);

        }}

        statusFilter={page.statusFilter}

        hasListFilters={page.hasListFilters}

        listFilters={page.listFilters}

        documentQuery={page.documentQuery}

        clearFilterTo={page.clearFilterTo}

        clearListFiltersTo={page.clearListFiltersTo}

        clearSearchTo={page.clearSearchTo}

        sortMode={page.sortMode}

        onSortChange={page.setSortMode}

        uploadAllowed={page.uploadAllowed}

        isMemberReadOnly={page.isMemberReadOnly}

        uploading={page.uploading}

        inlineError={inlineError}

        deletingDocId={page.deletingDocId}

        onClearInlineErrors={page.clearInlineErrors}

        onRefresh={() => void page.loadPage()}

        onUpload={(files) => void page.handleUpload(files)}

        onRequestDelete={page.setDeleteTarget}

        onRetry={async (docId) => {

          await page.handleRetryDocument(docId);

        }}

        onVisibilityToast={(message) => page.showToast(message)}

      />



      <EditKnowledgeBaseDialog

        kb={page.kb}

        open={page.editOpen}

        onOpenChange={page.setEditOpen}

        onUpdated={page.handleKbUpdated}

      />



      <DeleteDocumentDialog

        doc={page.deleteTarget}

        open={page.deleteTarget !== null}

        deleting={page.deletingDocId !== null}

        onOpenChange={(open) => {

          if (!open && page.deletingDocId === null) page.setDeleteTarget(null);

        }}

        onConfirm={() => void page.handleDeleteConfirm()}

      />



      <Toast message={page.toast?.message ?? null} onDismiss={page.dismissToast} />

    </div>

  );

}


