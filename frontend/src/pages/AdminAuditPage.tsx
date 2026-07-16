import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AuditLogFilters,
  buildAuditQueryFromFilters,
  EMPTY_AUDIT_FILTERS,
  type AuditLogFilterValues,
} from "@/components/admin/AuditLogFilters";
import { AuditLogTable } from "@/components/admin/AuditLogTable";
import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { SectionTitle } from "@/components/common/SectionTitle";
import { Button } from "@/components/ui/button";
import { fetchAuditLogs, type AuditLog } from "@/lib/audit-api";

const PAGE_SIZE = 20;

export function AdminAuditPage() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftFilters, setDraftFilters] =
    useState<AuditLogFilterValues>(EMPTY_AUDIT_FILTERS);
  const [appliedFilters, setAppliedFilters] =
    useState<AuditLogFilterValues>(EMPTY_AUDIT_FILTERS);
  const isFirstLoad = useRef(true);

  const pageCount = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  );

  const loadLogs = useCallback(
    async (options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false;

      if (silent) setRefreshing(true);
      else {
        setLoading(true);
        setError(null);
      }

      try {
        const data = await fetchAuditLogs(
          buildAuditQueryFromFilters(appliedFilters, page, PAGE_SIZE),
        );
        setItems(data.items);
        setTotal(data.total);
        if (!silent) setError(null);
      } catch (err) {
        if (!silent) {
          setItems([]);
          setTotal(0);
          setError(err instanceof Error ? err.message : "加载失败");
        }
      } finally {
        if (silent) setRefreshing(false);
        else setLoading(false);
      }
    },
    [appliedFilters, page],
  );

  useEffect(() => {
    const silent = !isFirstLoad.current;
    void loadLogs({ silent }).finally(() => {
      isFirstLoad.current = false;
    });

    document.title = "操作审计 · 睿阁";
    const metaDescription = document.querySelector('meta[name="description"]') as HTMLMetaElement | null;
    if (metaDescription) {
      metaDescription.content = "查看团队关键操作记录，登录、上传、删文档、成员变更等行为均在此留痕。";
    }
  }, [loadLogs]);

  function handleApplyFilters() {
    setAppliedFilters({ ...draftFilters });
    setPage(1);
  }

  function handleResetFilters() {
    const empty = { ...EMPTY_AUDIT_FILTERS };
    setDraftFilters(empty);
    setAppliedFilters(empty);
    setPage(1);
  }

  function handlePageChange(nextPage: number) {
    setPage(nextPage);
  }

  if (loading) {
    return (
      <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7 space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-border/70" />
        <div className="h-24 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
        <div className="h-64 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
        <AlertBanner
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void loadLogs()}>
              重试
            </Button>
          }
        >
          {error}
        </AlertBanner>
      </div>
    );
  }

  return (
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7 space-y-4">
      <SectionTitle
        label="操作审计"
        en="AUDIT LOG"
        trailing={
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={refreshing}
            onClick={() => void loadLogs({ silent: true })}
          >
            {refreshing ? "刷新中…" : "刷新"}
          </Button>
        }
      />

      <AuditLogFilters
        values={draftFilters}
        onChange={setDraftFilters}
        onApply={handleApplyFilters}
        onReset={handleResetFilters}
        applying={refreshing}
      />

      <AuditLogTable items={items} />

      <DocumentListPagination
        page={page}
        pageCount={pageCount}
        total={total}
        pageSize={PAGE_SIZE}
        onPageChange={handlePageChange}
        itemUnit="条"
      />
    </div>
  );
}
