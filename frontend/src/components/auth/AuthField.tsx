import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { ReactNode } from "react";

import { PasswordStrengthBar } from "@/components/auth/PasswordStrengthBar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface AuthFieldProps {
  id: string;
  label: ReactNode;
  /** 标签行右侧附加（如「忘记密码？」），不放入 <label> 以免嵌套可聚焦元素 */
  labelAccessory?: ReactNode;
  type?: React.ComponentProps<"input">["type"];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  error?: string;
  hint?: string;
  maxLength?: number;
  showPasswordToggle?: boolean;
  showStrength?: boolean;
}

export function AuthField({
  id,
  label,
  labelAccessory,
  type = "text",
  value,
  onChange,
  placeholder,
  autoComplete,
  error,
  hint,
  maxLength,
  showPasswordToggle = false,
  showStrength = false,
}: AuthFieldProps) {
  const [passwordVisible, setPasswordVisible] = useState(false);
  const isPasswordField = type === "password";
  const inputType =
    isPasswordField && showPasswordToggle
      ? passwordVisible
        ? "text"
        : "password"
      : type;

  return (
    <div>
      <div className="mb-1.5 flex w-full items-baseline justify-between gap-2">
        <Label
          htmlFor={id}
          className="text-[13px] font-medium text-[var(--auth-text)]"
        >
          {label}
        </Label>
        {labelAccessory}
      </div>
      <div className={cn(isPasswordField && showPasswordToggle && "relative")}>
        <Input
          id={id}
          type={inputType}
          autoComplete={autoComplete}
          value={value}
          maxLength={maxLength}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          aria-invalid={Boolean(error)}
          aria-describedby={
            error ? `${id}-error` : hint ? `${id}-hint` : undefined
          }
          className={cn(
            "auth-input h-11 rounded-[8px] border-[var(--auth-line)] bg-[var(--auth-field-bg)] text-[var(--auth-text)] placeholder:text-[color:#B5A8A2]",
            error && "border-[var(--status-err-border)] focus-visible:ring-[var(--status-err-border)]",
            isPasswordField && showPasswordToggle && "pr-10",
          )}
        />
        {isPasswordField && showPasswordToggle && (
          <button
            type="button"
            className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-[var(--auth-muted)] transition-colors hover:bg-[color:rgb(203_107_61/0.08)] hover:text-[var(--auth-action)]"
            onClick={() => setPasswordVisible((v) => !v)}
            aria-label={passwordVisible ? "隐藏密码" : "显示密码"}
          >
            {passwordVisible ? (
              <EyeOff className="h-[18px] w-[18px]" aria-hidden />
            ) : (
              <Eye className="h-[18px] w-[18px]" aria-hidden />
            )}
          </button>
        )}
      </div>
      {showStrength && isPasswordField && (
        <PasswordStrengthBar password={value} />
      )}
      {error ? (
        <p
          id={`${id}-error`}
          className="mt-1.5 text-xs text-[var(--status-err-text)]"
          role="alert"
        >
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-[var(--auth-muted)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

interface AuthFormSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export function AuthFormSection({
  title,
  description,
  children,
}: AuthFormSectionProps) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-xs font-medium text-[var(--auth-text)]">{title}</h3>
        {description && (
          <p className="mt-0.5 text-xs text-[var(--auth-muted)]">
            {description}
          </p>
        )}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

interface AuthFormAlertProps {
  message: string;
  action?: { label: string; onClick: () => void };
}

export function AuthFormAlert({ message, action }: AuthFormAlertProps) {
  return (
    <div
      role="alert"
      className="rounded-md border border-[var(--status-err-border)] bg-[var(--status-err-bg)] px-3 py-2 text-sm text-[var(--status-err-text)]"
    >
      <p>{message}</p>
      {action && (
        <button
          type="button"
          className="mt-1 font-medium underline"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
