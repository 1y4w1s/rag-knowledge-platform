import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  AuditLogFilters,
  buildAuditQueryFromFilters,
  EMPTY_AUDIT_FILTERS,
  hasActiveAuditFilters,
  type AuditLogFilterValues,
} from "@/components/admin/AuditLogFilters";
import { AuditLogTable } from "@/components/admin/AuditLogTable";
import { useAuditFilterOptions } from "@/components/admin/useAuditFilterOptions";
import { DocumentListPagination } from "@/components/knowledge-bases/DocumentListPagination";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { SectionTitle } from "@/components/common/SectionTitle";
import { Button } from "@/components/ui/button";
import { fetchAuditLogs, type AuditLog } from "@/lib/audit-api";

const PAGE_SIZE = 20;
const shell = "mx-auto max-w-[1180px] px-7 pb-16 pt-7";

export function AdminAuditPage() {
  const { kbOptions, actorOptions } = useAuditFilterOptions();
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
  const filtersActive = hasActiveAuditFilters(appliedFilters);

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
  }, [loadLogs]);

  if (loading) {
    return (
      <div className={`${shell} space-y-4`}>
        <div className="h-8 w-48 animate-pulse rounded bg-border/70" />
        <div className="h-24 animate-pulse rounded-[14px] border border-[var(--line2)] bg-white/60" />
        <div className="h-64 animate-pulse rounded-[14px] border border-[var(--line2)] bg-white/60" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={shell}>
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
    <div className={`${shell} space-y-4`}>
      <SectionTitle
        label="操作审计"
        en="AUDIT"
        tone="quiet"
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
        onApply={() => {
          setAppliedFilters({ ...draftFilters });
          setPage(1);
        }}
        onReset={() => {
          const empty = { ...EMPTY_AUDIT_FILTERS };
          setDraftFilters(empty);
          setAppliedFilters(empty);
          setPage(1);
        }}
        applying={refreshing}
        kbOptions={kbOptions}
        actorOptions={actorOptions}
      />

      <AuditLogTable
        items={items}
        emptyMode={filtersActive ? "filtered" : "none"}
      />

      {items.length > 0 ? (
        <DocumentListPagination
          page={page}
          pageCount={pageCount}
          total={total}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          itemUnit="条"
        />
      ) : null}
    </div>
  );
}
