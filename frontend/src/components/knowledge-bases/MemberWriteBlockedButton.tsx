import { Button, type ButtonProps } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type MemberWriteBlockedButtonProps = Omit<ButtonProps, "onClick" | "disabled"> & {
  onBlocked: () => void;
};

/** Gray clickable control for member write attempts — shows toast via onBlocked (UX-4). */
export function MemberWriteBlockedButton({
  onBlocked,
  className,
  ...props
}: MemberWriteBlockedButtonProps) {
  return (
    <Button
      type="button"
      className={cn("cursor-not-allowed opacity-60", className)}
      onClick={onBlocked}
      {...props}
    />
  );
}
