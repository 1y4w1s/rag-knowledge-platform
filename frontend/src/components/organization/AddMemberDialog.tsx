import { useEffect, useId } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface AddMemberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (email: string) => Promise<void>;
  submitting?: boolean;
}

export function AddMemberDialog({
  open,
  onOpenChange,
  onSubmit,
  submitting = false,
}: AddMemberDialogProps) {
  const titleId = useId();
  const inputId = useId();

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, submitting, onOpenChange]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const email = (form.elements.namedItem("email") as HTMLInputElement).value.trim();
    if (!email) return;
    await onSubmit(email);
    form.reset();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!submitting) onOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-black/30" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-xl border border-[var(--line2)] bg-white p-6 shadow-md"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold tracking-[0.02em] text-foreground"
        >
          添加成员
        </h2>
        <p className="mt-2 text-sm text-muted">
          输入已注册用户的邮箱，将其加入团队并赋予成员权限。
        </p>

        <form className="mt-4 space-y-4" onSubmit={(e) => void handleSubmit(e)}>
          <div>
            <Label htmlFor={inputId} className="settings-field-label">
              邮箱
            </Label>
            <Input
              id={inputId}
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="member@example.com"
              disabled={submitting}
              className="settings-field-input h-10"
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "添加中…" : "添加"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
