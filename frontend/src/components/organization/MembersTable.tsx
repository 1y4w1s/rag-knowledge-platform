import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import {
  formatJoinedAt,
  type OrganizationMember,
} from "@/lib/organization-api";
import { MemberRoleActions } from "@/components/organization/MemberRoleActions";
import { RoleBadge } from "@/components/organization/RoleBadge";
import { Avatar, displayNameFromEmail } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/button";

interface MembersTableProps {
  members: OrganizationMember[];
  readOnly?: boolean;
  isOwner?: boolean;
  currentUserId?: string;
  removingUserId?: string | null;
  changingRoleUserId?: string | null;
  onRequestRemove?: (member: OrganizationMember) => void;
  onPromote?: (member: OrganizationMember) => void;
  onDemote?: (member: OrganizationMember) => void;
  onRequestTransfer?: () => void;
}

const ROW_HEIGHT = 64;

export function MembersTable({
  members,
  readOnly = false,
  isOwner = false,
  currentUserId,
  removingUserId = null,
  changingRoleUserId = null,
  onRequestRemove,
  onPromote,
  onDemote,
  onRequestTransfer,
}: MembersTableProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: members.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  });

  const gridCols = readOnly
    ? "grid grid-cols-[minmax(0,1fr)_6.5rem_8rem] items-center gap-3 px-1"
    : "grid grid-cols-[minmax(0,1fr)_6.5rem_8rem_10rem] items-center gap-3 px-1";

  return (
    <div className="org-members-table">
      <div
        role="row"
        className={`${gridCols} border-b border-[var(--line2)] py-2.5 text-xs font-medium text-muted`}
      >
        <div role="columnheader">成员</div>
        <div role="columnheader">角色</div>
        <div role="columnheader">加入时间</div>
        {!readOnly ? (
          <div role="columnheader" className="text-right" aria-label="操作" />
        ) : null}
      </div>

      {members.length === 0 ? (
        <div className="px-1 py-10 text-sm text-muted">暂无成员</div>
      ) : (
        <div
          ref={parentRef}
          className="max-h-[62vh] overflow-auto"
          role="rowgroup"
        >
          <div
            style={{
              height: virtualizer.getTotalSize(),
              position: "relative",
            }}
          >
            {virtualizer.getVirtualItems().map((vItem) => {
              const member = members[vItem.index];
              const isProtectedAdmin =
                member.role === "admin" || member.is_owner;
              const removing = removingUserId === member.user_id;
              return (
                <div
                  key={member.user_id}
                  role="row"
                  className="absolute left-0 top-0 w-full"
                  style={{
                    height: ROW_HEIGHT,
                    transform: `translateY(${vItem.start}px)`,
                  }}
                >
                  <div
                    className={`${gridCols} h-full border-b border-[var(--line2)] py-2`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <Avatar name={member.email} size="md" />
                      <div className="min-w-0">
                        <div className="truncate text-[0.85rem] font-medium text-foreground">
                          {displayNameFromEmail(member.email)}
                        </div>
                        <div
                          className="truncate text-[0.72rem] text-muted"
                          title={member.email}
                        >
                          {member.email}
                        </div>
                      </div>
                    </div>
                    <div>
                      <RoleBadge
                        role={member.role}
                        isOwner={member.is_owner}
                      />
                    </div>
                    <div className="whitespace-nowrap text-[0.78rem] text-muted">
                      {formatJoinedAt(member.joined_at)}
                    </div>
                    {!readOnly ? (
                      <div className="text-right">
                        {member.is_owner ? (
                          isOwner && member.user_id === currentUserId ? (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2 text-[0.8125rem] text-muted hover:text-foreground"
                              onClick={() => onRequestTransfer?.()}
                            >
                              转让所有权
                            </Button>
                          ) : (
                            <span className="text-muted">—</span>
                          )
                        ) : isOwner ? (
                          <div className="flex flex-wrap items-center justify-end gap-1">
                            <MemberRoleActions
                              member={member}
                              changingUserId={changingRoleUserId}
                              onPromote={onPromote}
                              onDemote={onDemote}
                            />
                            {member.role === "member" ? (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={removing}
                                className="h-8 px-2 text-[0.8125rem] text-[var(--bad)] hover:bg-[color:var(--status-err-bg)] hover:text-[var(--bad)]"
                                onClick={() => onRequestRemove?.(member)}
                              >
                                {removing ? "移除中…" : "移除"}
                              </Button>
                            ) : null}
                          </div>
                        ) : isProtectedAdmin ? (
                          <span className="text-muted">—</span>
                        ) : (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={removing}
                            className="h-8 px-2 text-[0.8125rem] text-[var(--bad)] hover:bg-[color:var(--status-err-bg)] hover:text-[var(--bad)]"
                            onClick={() => onRequestRemove?.(member)}
                          >
                            {removing ? "移除中…" : "移除"}
                          </Button>
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
