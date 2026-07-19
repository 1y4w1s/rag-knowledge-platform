import { AUDIT_ACTION_OPTIONS } from "@/lib/audit-labels";
import { Button } from "@/components/ui/button";
import { Select, type SelectOption } from "@/components/ui/Select";

export interface AuditLogFilterValues {
  action: string;
  kbId: string;
  actorUserId: string;
  ip: string;
  dateFrom: string;
  dateTo: string;
}

interface AuditLogFiltersProps {
  values: AuditLogFilterValues;
  onChange: (values: AuditLogFilterValues) => void;
  onApply: () => void;
  onReset: () => void;
  applying?: boolean;
  kbOptions?: SelectOption[];
  actorOptions?: SelectOption[];
}

const inputClass =
  "h-9 w-full rounded-md border border-[var(--line2)] bg-white px-2.5 text-sm text-foreground outline-none transition-colors focus:border-[var(--action)] focus:ring-[3px] focus:ring-[rgba(203,107,61,0.12)]";

const fieldLabelClass =
  "mb-1.5 block text-[11px] font-semibold text-[var(--mut)]";

export function AuditLogFilters({
  values,
  onChange,
  onApply,
  onReset,
  applying = false,
  kbOptions = [],
  actorOptions = [],
}: AuditLogFiltersProps) {
  return (
    <form
      className="relative z-[2] mb-3.5 flex flex-wrap items-end gap-3 overflow-visible rounded-[14px] border border-[var(--line2)] bg-gradient-to-br from-white to-[#f7f4f0] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="min-w-[9rem] flex-1">
        <label htmlFor="audit-filter-action" className={fieldLabelClass}>
          操作类型
        </label>
        <Select
          id="audit-filter-action"
          value={values.action}
          options={[{ value: "", label: "全部" }, ...AUDIT_ACTION_OPTIONS]}
          onChange={(action) => onChange({ ...values, action })}
        />
      </div>

      <div className="min-w-[10rem] flex-1">
        <label htmlFor="audit-filter-kb" className={fieldLabelClass}>
          资料库
        </label>
        <Select
          id="audit-filter-kb"
          value={values.kbId}
          options={[{ value: "", label: "全部资料库" }, ...kbOptions]}
          onChange={(kbId) => onChange({ ...values, kbId })}
        />
      </div>

      <div className="min-w-[10rem] flex-1">
        <label htmlFor="audit-filter-actor" className={fieldLabelClass}>
          操作者
        </label>
        <Select
          id="audit-filter-actor"
          value={values.actorUserId}
          options={[{ value: "", label: "全部成员" }, ...actorOptions]}
          onChange={(actorUserId) => onChange({ ...values, actorUserId })}
        />
      </div>

      <div className="min-w-[7.5rem] flex-[0.8]">
        <label htmlFor="audit-filter-ip" className={fieldLabelClass}>
          IP
        </label>
        <input
          id="audit-filter-ip"
          type="text"
          value={values.ip}
          onChange={(event) => onChange({ ...values, ip: event.target.value })}
          placeholder="可选"
          className={inputClass}
          autoComplete="off"
        />
      </div>

      <div className="min-w-[8rem] flex-[0.7]">
        <label htmlFor="audit-filter-from" className={fieldLabelClass}>
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

      <div className="min-w-[8rem] flex-[0.7]">
        <label htmlFor="audit-filter-to" className={fieldLabelClass}>
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
    actor_user_id?: string;
    ip?: string;
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

  const actorUserId = values.actorUserId.trim();
  if (actorUserId) query.actor_user_id = actorUserId;

  const ip = values.ip.trim();
  if (ip) query.ip = ip;

  if (values.dateFrom) {
    query.created_from = `${values.dateFrom}T00:00:00`;
  }
  if (values.dateTo) {
    query.created_to = `${values.dateTo}T23:59:59.999`;
  }

  return query;
}

export function hasActiveAuditFilters(values: AuditLogFilterValues): boolean {
  return Boolean(
    values.action.trim() ||
      values.kbId.trim() ||
      values.actorUserId.trim() ||
      values.ip.trim() ||
      values.dateFrom ||
      values.dateTo,
  );
}

export const EMPTY_AUDIT_FILTERS: AuditLogFilterValues = {
  action: "",
  kbId: "",
  actorUserId: "",
  ip: "",
  dateFrom: "",
  dateTo: "",
};
