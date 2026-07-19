import { OrgConfirmDialog } from "@/components/organization/OrgConfirmDialog";
import type { OrganizationMember } from "@/lib/organization-api";

interface RemoveMemberDialogProps {
  member: OrganizationMember | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  removing?: boolean;
}

export function RemoveMemberDialog({
  member,
  open,
  onOpenChange,
  onConfirm,
  removing = false,
}: RemoveMemberDialogProps) {
  if (!member) return null;

  return (
    <OrgConfirmDialog
      open={open}
      title="移除成员"
      description={`确定将「${member.email}」移出团队？`}
      confirmLabel="确认移除"
      confirming={removing}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
    />
  );
}
