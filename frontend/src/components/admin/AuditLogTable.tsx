import { Link } from "react-router-dom";

import type { AuditLog } from "@/lib/audit-api";
import {
  formatAuditDetails,
  formatAuditTimestamp,
  shortenUuid,
} from "@/lib/audit-api";
import { formatAuditAction, isFailedAuditAction } from "@/lib/audit-labels";

interface AuditLogTableProps {
  items: AuditLog[];
  emptyMode?: "none" | "filtered";
}

function actorLabel(row: AuditLog): string {
  if (row.actor_email) return row.actor_email;
  if (row.details && typeof row.details.email === "string") {
    return row.details.email;
  }
  if (row.actor_user_id) return shortenUuid(row.actor_user_id);
  return "—";
}

function KbCell({ row }: { row: AuditLog }) {
  if (!row.kb_id) {
    return <span className="text-[var(--mut)]">—</span>;
  }
  const label = row.kb_name?.trim() || shortenUuid(row.kb_id);
  return (
    <Link
      to={`/knowledge-bases/${row.kb_id}`}
      className="font-semibold text-[var(--action)] no-underline hover:underline"
      title={row.kb_name ?? row.kb_id}
    >
      {label}
    </Link>
  );
}

export function AuditLogTable({
  items,
  emptyMode = "none",
}: AuditLogTableProps) {
  if (items.length === 0) {
    const filtered = emptyMode === "filtered";
    return (
      <div className="border-t border-[var(--line2)] py-5">
        <p className="font-serif text-base text-foreground">
          {filtered ? "没有符合条件的记录" : "暂无审计记录"}
        </p>
        <p className="mt-2 text-sm text-[var(--mut)]">
          {filtered
            ? "试试放宽日期或清空操作类型 / 资料库筛选。"
            : "团队内尚无记入审计的操作。"}
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-[14px] border border-[var(--line2)] bg-[color-mix(in_srgb,var(--surf)_72%,transparent)] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
      <table className="data-table data-table-quiet">
        <thead>
          <tr>
            <th scope="col">时间</th>
            <th scope="col">操作</th>
            <th scope="col">资料库</th>
            <th scope="col">操作者</th>
            <th scope="col">IP</th>
            <th scope="col">详情</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const details = formatAuditDetails(row.details);
            return (
              <tr key={row.id}>
                <td className="whitespace-nowrap text-[var(--mut)]">
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
                <td>
                  <KbCell row={row} />
                </td>
                <td
                  className="max-w-[11rem] truncate text-sm"
                  title={actorLabel(row)}
                >
                  {actorLabel(row)}
                </td>
                <td className="whitespace-nowrap text-[var(--mut)]">
                  {row.ip?.trim() || "—"}
                </td>
                <td
                  className="max-w-[12rem] truncate text-sm text-[var(--mut)]"
                  title={details}
                >
                  {details}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
