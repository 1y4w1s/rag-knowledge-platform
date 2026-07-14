import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { CreateKnowledgeBaseDialog } from "@/components/knowledge-bases/CreateKnowledgeBaseDialog";
import { DeleteKnowledgeBaseDialog } from "@/components/knowledge-bases/DeleteKnowledgeBaseDialog";
import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import { EditKnowledgeBaseDialog } from "@/components/knowledge-bases/EditKnowledgeBaseDialog";
import {
  KbListSearchBar,
  KbListSearchEmptyPanel,
} from "@/components/knowledge-bases/KbListSearchBar";
import { MemberWriteBlockedButton } from "@/components/knowledge-bases/MemberWriteBlockedButton";
import { MemberReadOnlyHint } from "@/components/knowledge-bases/MemberReadOnlyHint";
import { EmptyStateV44, KBS_SCENE, PATHS } from "@/components/ui/EmptyState";
import { KnowledgeBaseCard } from "@/components/knowledge-bases/KnowledgeBaseCard";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Toast, useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth-context";
import {
  canWriteKnowledgeBase,
  isTeamMemberReadOnly,
} from "@/lib/org-permissions";
import { showMemberWriteBlockedToast } from "@/lib/member-write-message";
import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";
import { clearRecentKbId, getRecentKbId } from "@/lib/workspace-storage";
import {
  buildUrlWithoutKbListQuery,
  buildUrlWithKbListPage,
  KB_LIST_PAGE_SIZE,
  parseKbListPage,
  parseKbListQuery,
  parseKbListSort,
} from "@/lib/kb-list-utils";
import {
  deleteKnowledgeBase,
  fetchKnowledgeBasesPage,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";

function KbGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {[1, 2].map((i) => (
        <div
          key={i}
          className="h-[120px] animate-pulse rounded-xl border border-[var(--line2)] bg-white/60"
        />
      ))}
    </div>
  );
}

export function KnowledgeBasesPage() {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const canCreateKb = canWriteKnowledgeBase(user, workspace);
  const isMemberReadOnly = isTeamMemberReadOnly(user, workspace);
  const canDeleteKb = canCreateKb;
  const canEditKb = canCreateKb;
  const { toast, show: showToast, dismiss: dismissToast } = useToast();
  const notifyMemberWriteBlocked = useCallback(() => {
    showMemberWriteBlockedToast(showToast);
  }, [showToast]);
  const prevWorkspaceRef = useRef(workspace);
  const prevDepartmentRef = useRef(departmentId);

  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<KnowledgeBase | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeBase | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const listQuery = parseKbListQuery(search);
  const sortMode = parseKbListSort(search);
  const page = parseKbListPage(search);
  const clearSearchTo = buildUrlWithoutKbListQuery(pathname, search);
  const pageCount = Math.max(1, Math.ceil(total / KB_LIST_PAGE_SIZE));
  const hasListContext = total > 0 || listQuery.length > 0;

  const loadList = useCallback(async () => {
    const expectedGen = generation;
    const expectedDeptGen = departmentGeneration;
    const requestWorkspace = workspace;
    const requestDepartmentId = workspace === "personal" ? null : departmentId;
    const requestPage = page;
    setLoading(true);
    setError(null);
    setItems([]);
    try {
      const data = await fetchKnowledgeBasesPage(
        {
          limit: KB_LIST_PAGE_SIZE,
          offset: (requestPage - 1) * KB_LIST_PAGE_SIZE,
          q: listQuery || undefined,
          sort: sortMode,
        },
        {
          expectedGen,
          getCurrentGeneration: getGeneration,
          expectedDepartmentGen: expectedDeptGen,
          getCurrentDepartmentGeneration: getDepartmentGeneration,
          workspace: requestWorkspace,
          departmentId: requestDepartmentId,
        },
      );
      if (data === null) return;
      if (getGeneration() !== expectedGen) return;
      if (getDepartmentGeneration() !== expectedDeptGen) return;
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      if (getGeneration() !== expectedGen) return;
      if (getDepartmentGeneration() !== expectedDeptGen) return;
      setItems([]);
      setTotal(0);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (
        getGeneration() === expectedGen &&
        getDepartmentGeneration() === expectedDeptGen
      ) {
        setLoading(false);
      }
    }
  }, [
    workspace,
    generation,
    getGeneration,
    departmentId,
    departmentGeneration,
    getDepartmentGeneration,
    listQuery,
    sortMode,
    page,
  ]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    document.title = "睿阁 · 资料库";
    const meta = document.querySelector('meta[name="description"]');
    if (meta) {
      meta.setAttribute(
        "content",
        "在睿阁整理文档集合，供 AI 带引用回答。创建、搜索、管理你的知识库。",
      );
    }
  }, []);

  useEffect(() => {
    if (loading || total === 0) return;
    if (page > pageCount) {
      navigate(buildUrlWithKbListPage(pathname, search, pageCount), {
        replace: true,
      });
    }
  }, [loading, total, page, pageCount, pathname, search, navigate]);

  useEffect(() => {
    if (prevWorkspaceRef.current === workspace) return;
    prevWorkspaceRef.current = workspace;
    if (listQuery || page > 1) {
      navigate(clearSearchTo, { replace: true });
    }
  }, [workspace, listQuery, page, clearSearchTo, navigate]);

  useEffect(() => {
    if (prevDepartmentRef.current === departmentId) return;
    prevDepartmentRef.current = departmentId;
    if (listQuery || page > 1) {
      navigate(clearSearchTo, { replace: true });
    }
  }, [departmentId, listQuery, page, clearSearchTo, navigate]);

  const goToPage = useCallback(
    (nextPage: number) => {
      const clamped = Math.min(Math.max(nextPage, 1), pageCount);
      navigate(buildUrlWithKbListPage(pathname, search, clamped));
    },
    [navigate, pageCount, pathname, search],
  );

  function handleDeleteClick(kb: KnowledgeBase) {
    setDeleteTarget(kb);
  }

  function handleEditClick(kb: KnowledgeBase) {
    setEditTarget(kb);
  }

  function handleEditUpdated(updated: KnowledgeBase) {
    setItems((prev) =>
      prev.map((item) => (item.id === updated.id ? updated : item)),
    );
    setEditTarget(null);
  }

  function handleCreated(kb: KnowledgeBase) {
    navigate(`/knowledge-bases/${kb.id}`);
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;

    setDeletingId(deleteTarget.id);
    setError(null);
    try {
      await deleteKnowledgeBase(deleteTarget.id);
      if (getRecentKbId(workspace) === deleteTarget.id) {
        clearRecentKbId(workspace);
      }
      setDeleteTarget(null);
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div>
      <header className="mb-[18px] flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-serif text-[1.05rem] font-semibold tracking-[0.02em] text-foreground">
            资料库
          </h2>
          <p className="mt-1 text-[0.78rem] text-muted">
            整理文档集合，供 AI 带引用回答
          </p>
        </div>
        {canCreateKb ? (
          <Button type="button" size="sm" variant="brand" onClick={() => setDialogOpen(true)}>
            + 新建资料库
          </Button>
        ) : isMemberReadOnly ? (
          <MemberWriteBlockedButton size="sm" onBlocked={notifyMemberWriteBlocked}>
            + 新建资料库
          </MemberWriteBlockedButton>
        ) : null}
      </header>

      {error && (
        <AlertBanner
          className="mb-4"
          action={
            <Button type="button" variant="outline" size="sm" onClick={loadList}>
              重试
            </Button>
          }
        >
          {error}
        </AlertBanner>
      )}

      {isMemberReadOnly && total > 0 && <MemberReadOnlyHint />}

      {loading ? (
        <KbGridSkeleton />
      ) : !hasListContext ? (
        <EmptyStateV44
          scene={{
            ...KBS_SCENE,
            ctaPrimary: {
              label: canCreateKb ? "新建第一个资料库" : "联系管理员建库",
              iconPath: PATHS.plus,
              onClick: canCreateKb
                ? () => setDialogOpen(true)
                : notifyMemberWriteBlocked,
            },
            ctaSecondary: {
              label: "查看概览",
              iconPath: PATHS.doc,
              onClick: () => navigate("/dashboard"),
            },
          }}
        />
      ) : (
        <>
          <KbListSearchBar
            pathname={pathname}
            search={search}
            query={listQuery}
            sortMode={sortMode}
            resultCount={total}
          />

          {listQuery && total === 0 ? (
            <KbListSearchEmptyPanel
              query={listQuery}
              clearTo={clearSearchTo}
            />
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {items.map((kb) => (
                  <KnowledgeBaseCard
                    key={kb.id}
                    kb={kb}
                    canEdit={canEditKb}
                    canDelete={canDeleteKb}
                    deleting={deletingId === kb.id}
                    onEdit={handleEditClick}
                    onDelete={handleDeleteClick}
                    onMemberWriteBlocked={
                      isMemberReadOnly ? notifyMemberWriteBlocked : undefined
                    }
                  />
                ))}
              </div>
              <DocumentListPagination
                page={page}
                pageCount={pageCount}
                total={total}
                pageSize={KB_LIST_PAGE_SIZE}
                itemUnit="个资料库"
                onPageChange={goToPage}
              />
            </>
          )}
        </>
      )}

      <EditKnowledgeBaseDialog
        kb={editTarget}
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEditTarget(null);
        }}
        onUpdated={handleEditUpdated}
      />

      <DeleteKnowledgeBaseDialog
        kb={deleteTarget}
        open={deleteTarget !== null}
        deleting={deletingId !== null}
        onOpenChange={(open) => {
          if (!open && deletingId === null) setDeleteTarget(null);
        }}
        onConfirm={() => void handleDeleteConfirm()}
      />

      {canCreateKb && (
        <CreateKnowledgeBaseDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          onCreated={handleCreated}
          workspace={workspace}
          departmentId={workspace === "personal" ? null : departmentId}
          user={user}
        />
      )}

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </div>
  );
}
