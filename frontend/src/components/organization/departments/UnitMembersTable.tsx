import { formatJoinedAt } from "@/lib/organization-api";
import {
  formatUnitRoleLabel,
  type OrgUnitMember,
  type UnitRole,
} from "@/lib/org-units-api";
import { Button } from "@/components/ui/button";

interface UnitMembersTableProps {
  members: OrgUnitMember[];
  updatingUserId?: string | null;
  removingUserId?: string | null;
  onSetRole?: (member: OrgUnitMember, role: UnitRole) => void;
  onSetPrimary?: (member: OrgUnitMember) => void;
  onRemove?: (member: OrgUnitMember) => void;
}

const ghostQuiet =
  "h-8 px-2 text-[0.8125rem] text-muted hover:text-foreground";
const ghostDanger =
  "h-8 px-2 text-[0.8125rem] text-[var(--bad)] hover:bg-[color:var(--status-err-bg)] hover:text-[var(--bad)]";

export function UnitMembersTable({
  members,
  updatingUserId = null,
  removingUserId = null,
  onSetRole,
  onSetPrimary,
  onRemove,
}: UnitMembersTableProps) {
  if (members.length === 0) {
    return <p className="py-4 text-sm text-muted">暂无成员</p>;
  }

  return (
    <table className="data-table data-table-quiet">
      <thead>
        <tr>
          <th scope="col">邮箱</th>
          <th scope="col">部门角色</th>
          <th scope="col">主部门</th>
          <th scope="col">加入时间</th>
          <th scope="col" aria-label="操作" />
        </tr>
      </thead>
      <tbody>
        {members.map((member) => {
          const updating = updatingUserId === member.user_id;
          const removing = removingUserId === member.user_id;
          return (
            <tr key={member.user_id}>
              <td className="text-foreground">{member.email}</td>
              <td>
                <span className="org-unit-role-badge">
                  {formatUnitRoleLabel(member.role)}
                </span>
              </td>
              <td className="text-muted">
                {member.is_primary ? (
                  <span className="text-foreground">是</span>
                ) : (
                  "否"
                )}
              </td>
              <td className="text-muted">{formatJoinedAt(member.joined_at)}</td>
              <td className="text-right">
                <div className="flex flex-wrap items-center justify-end gap-1">
                  {member.role === "unit_member" ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={updating || removing}
                      className={ghostQuiet}
                      onClick={() => onSetRole?.(member, "unit_admin")}
                    >
                      {updating ? "更新中…" : "升为管理员"}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={updating || removing}
                      className={ghostQuiet}
                      onClick={() => onSetRole?.(member, "unit_member")}
                    >
                      {updating ? "更新中…" : "降为成员"}
                    </Button>
                  )}
                  {!member.is_primary ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={updating || removing}
                      className={ghostQuiet}
                      onClick={() => onSetPrimary?.(member)}
                    >
                      {updating ? "更新中…" : "设为主部门"}
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={updating || removing}
                    className={ghostDanger}
                    onClick={() => onRemove?.(member)}
                  >
                    {removing ? "移出中…" : "移出"}
                  </Button>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
