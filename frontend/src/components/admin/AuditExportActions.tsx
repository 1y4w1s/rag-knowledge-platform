import { Button } from "@/components/ui/button";
import type { AuditExportFormat } from "@/lib/audit-api";

interface AuditExportActionsProps {
  exporting: AuditExportFormat | null;
  refreshing: boolean;
  onExport: (format: AuditExportFormat) => void;
  onRefresh: () => void;
}

/** 审计页导出 CSV/JSON + 刷新（筛选由父组件在 onExport 内带上）。 */
export function AuditExportActions({
  exporting,
  refreshing,
  onExport,
  onRefresh,
}: AuditExportActionsProps) {
  const busy = exporting !== null || refreshing;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() => onExport("csv")}
      >
        {exporting === "csv" ? "导出中…" : "导出 CSV"}
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={() => onExport("json")}
      >
        {exporting === "json" ? "导出中…" : "导出 JSON"}
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={busy}
        onClick={onRefresh}
      >
        {refreshing ? "刷新中…" : "刷新"}
      </Button>
    </div>
  );
}
