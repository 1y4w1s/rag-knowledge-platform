import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { PasswordStrengthBar } from "@/components/auth/PasswordStrengthBar";
import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface ChangePasswordFormProps {
  onSubmit: (currentPassword: string, newPassword: string) => Promise<void>;
}

interface FieldErrors {
  currentPassword?: string;
  newPassword?: string;
}

function SettingsPasswordField({
  id,
  label,
  value,
  onChange,
  placeholder,
  autoComplete,
  error,
  showStrength = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  error?: string;
  showStrength?: boolean;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <Label htmlFor={id} className="settings-field-label">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          placeholder={placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "settings-field-input pr-10",
            error && "border-[color:var(--status-err-border)] focus-visible:ring-[color:rgb(232_180_160/0.35)]",
          )}
        />
        <button
          type="button"
          className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:bg-nav-on hover:text-foreground"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "隐藏密码" : "显示密码"}
        >
          {visible ? (
            <EyeOff className="h-[18px] w-[18px]" aria-hidden />
          ) : (
            <Eye className="h-[18px] w-[18px]" aria-hidden />
          )}
        </button>
      </div>
      {showStrength && value ? <PasswordStrengthBar password={value} /> : null}
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-[color:var(--status-err-text)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function ChangePasswordForm({ onSubmit }: ChangePasswordFormProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!currentPassword.trim()) next.currentPassword = "请输入当前密码";
    if (!newPassword.trim()) {
      next.newPassword = "请输入新密码";
    } else if (newPassword.length < 8) {
      next.newPassword = "新密码至少 8 位";
    }
    return next;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await onSubmit(currentPassword, newPassword);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "保存失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SettingsFormCard title="修改密码">
      <form className="space-y-4" onSubmit={(e) => void handleSubmit(e)} noValidate>
        {formError ? (
          <div
            role="alert"
            className="rounded-md border border-[color:var(--status-err-border)] bg-[color:var(--status-err-bg)] px-3 py-2 text-sm text-[color:var(--status-err-text)]"
          >
            {formError}
          </div>
        ) : null}

        <SettingsPasswordField
          id="current-password"
          label="当前密码"
          value={currentPassword}
          onChange={setCurrentPassword}
          autoComplete="current-password"
          error={errors.currentPassword}
        />
        <SettingsPasswordField
          id="new-password"
          label="新密码"
          value={newPassword}
          onChange={setNewPassword}
          placeholder="至少 8 位"
          autoComplete="new-password"
          error={errors.newPassword}
          showStrength
        />

        <Button
          type="submit"
          variant="brand"
          className="mt-1 w-full sm:w-auto"
          disabled={submitting}
        >
          {submitting ? "保存中…" : "保存密码"}
        </Button>
      </form>
    </SettingsFormCard>
  );
}
