import { AUDIT_ACTION_OPTIONS } from "@/lib/audit-labels";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/Select";

export interface AuditLogFilterValues {
  action: string;
  kbId: string;
  dateFrom: string;
  dateTo: string;
}

interface AuditLogFiltersProps {
  values: AuditLogFilterValues;
  onChange: (values: AuditLogFilterValues) => void;
  onApply: () => void;
  onReset: () => void;
  applying?: boolean;
}

const inputClass =
  "h-9 rounded-md border border-[var(--line2)] bg-white px-2.5 text-sm text-foreground outline-none transition-colors focus:border-[var(--action)] focus:ring-1 focus:ring-[var(--action)]";

export function AuditLogFilters({
  values,
  onChange,
  onApply,
  onReset,
  applying = false,
}: AuditLogFiltersProps) {
  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-xl border border-[var(--line2)] bg-white/80 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="min-w-[10rem] flex-1">
        <label htmlFor="audit-filter-action" className="mb-1 block text-xs text-muted">
          操作类型
        </label>
        <Select
          id="audit-filter-action"
          value={values.action}
          options={[{ value: "", label: "全部" }, ...AUDIT_ACTION_OPTIONS]}
          onChange={(action) => onChange({ ...values, action })}
        />
      </div>

      <div className="min-w-[12rem] flex-1">
        <label htmlFor="audit-filter-kb" className="mb-1 block text-xs text-muted">
          资料库 ID
        </label>
        <input
          id="audit-filter-kb"
          type="text"
          value={values.kbId}
          onChange={(event) => onChange({ ...values, kbId: event.target.value })}
          placeholder="完整 UUID，可留空"
          className={`${inputClass} w-full font-mono text-[0.8125rem]`}
        />
      </div>

      <div>
        <label htmlFor="audit-filter-from" className="mb-1 block text-xs text-muted">
          起始日期
        </label>
        <input
          id="audit-filter-from"
          type="date"
          value={values.dateFrom}
          onChange={(event) =>
            onChange({ ...values, dateFrom: event.target.value })
          }
          className={inputClass}
        />
      </div>

      <div>
        <label htmlFor="audit-filter-to" className="mb-1 block text-xs text-muted">
          结束日期
        </label>
        <input
          id="audit-filter-to"
          type="date"
          value={values.dateTo}
          onChange={(event) =>
            onChange({ ...values, dateTo: event.target.value })
          }
          className={inputClass}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={applying}>
          {applying ? "查询中…" : "查询"}
        </Button>
        <Button type="button" variant="outline" size="sm" onClick={onReset}>
          重置
        </Button>
      </div>
    </form>
  );
}

export function buildAuditQueryFromFilters(
  values: AuditLogFilterValues,
  page: number,
  pageSize: number,
) {
  const query: {
    limit: number;
    offset: number;
    action?: string;
    kb_id?: string;
    created_from?: string;
    created_to?: string;
  } = {
    limit: pageSize,
    offset: (page - 1) * pageSize,
  };

  const action = values.action.trim();
  if (action) query.action = action;

  const kbId = values.kbId.trim();
  if (kbId) query.kb_id = kbId;

  if (values.dateFrom) {
    query.created_from = `${values.dateFrom}T00:00:00`;
  }
  if (values.dateTo) {
    query.created_to = `${values.dateTo}T23:59:59.999`;
  }

  return query;
}

export const EMPTY_AUDIT_FILTERS: AuditLogFilterValues = {
  action: "",
  kbId: "",
  dateFrom: "",
  dateTo: "",
};
