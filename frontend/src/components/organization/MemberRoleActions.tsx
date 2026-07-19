import type { OrganizationMember } from "@/lib/organization-api";
import { Button } from "@/components/ui/button";

interface MemberRoleActionsProps {
  member: OrganizationMember;
  changingUserId?: string | null;
  onPromote?: (member: OrganizationMember) => void;
  onDemote?: (member: OrganizationMember) => void;
}

export function MemberRoleActions({
  member,
  changingUserId = null,
  onPromote,
  onDemote,
}: MemberRoleActionsProps) {
  const changing = changingUserId === member.user_id;

  if (member.role === "member") {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={changing}
        className="h-8 px-2 text-[0.8125rem] text-muted hover:text-foreground"
        onClick={() => onPromote?.(member)}
      >
        {changing ? "处理中…" : "设为管理员"}
      </Button>
    );
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={changing}
      className="h-8 px-2 text-[0.8125rem] text-muted hover:text-foreground"
      onClick={() => onDemote?.(member)}
    >
      {changing ? "处理中…" : "降为成员"}
    </Button>
  );
}
