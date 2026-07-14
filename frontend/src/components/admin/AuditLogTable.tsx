import type { AuditLog } from "@/lib/audit-api";
import {
  formatAuditTimestamp,
  shortenUuid,
} from "@/lib/audit-api";
import { formatAuditAction, isFailedAuditAction } from "@/lib/audit-labels";

interface AuditLogTableProps {
  items: AuditLog[];
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details || Object.keys(details).length === 0) return "—";
  const filename = details.filename;
  if (typeof filename === "string") return filename;
  const name = details.name;
  if (typeof name === "string") return name;
  return JSON.stringify(details);
}

export function AuditLogTable({ items }: AuditLogTableProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--line2)] bg-white/60 px-6 py-12 text-center">
        <p className="font-serif text-base text-foreground">暂无审计记录</p>
        <p className="mt-2 text-sm text-muted">
          关键操作（登录、上传、删文档、成员变更等）会出现在这里。
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--line2)] bg-white/80">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">操作</th>
            <th scope="col">资料库</th>
            <th scope="col">操作者</th>
            <th scope="col">详情</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id}>
              <td className="whitespace-nowrap text-muted">
                {formatAuditTimestamp(row.created_at)}
              </td>
              <td>
                <span
                  className={`audit-tag${isFailedAuditAction(row.action) ? " err" : ""}`}
                  title={row.action}
                >
                  {formatAuditAction(row.action)}
                </span>
              </td>
              <td
                className="font-mono text-[0.8125rem] text-muted"
                title={row.kb_id ?? undefined}
              >
                {shortenUuid(row.kb_id)}
              </td>
              <td
                className="font-mono text-[0.8125rem] text-muted"
                title={row.actor_user_id ?? undefined}
              >
                {shortenUuid(row.actor_user_id)}
              </td>
              <td className="max-w-[12rem] truncate text-sm text-muted" title={formatDetails(row.details)}>
                {formatDetails(row.details)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
