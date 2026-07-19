import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface PasswordRequirementsProps {
  password: string;
}

interface Rule {
  label: string;
  check: (p: string) => boolean;
}

const RULES: Rule[] = [
  { label: "至少 8 位", check: (p) => p.length >= 8 },
  { label: "包含大写字母", check: (p) => /[A-Z]/.test(p) },
  { label: "包含小写字母", check: (p) => /[a-z]/.test(p) },
  { label: "包含数字", check: (p) => /\d/.test(p) },
  { label: "包含特殊字符（如 @ # $ %）", check: (p) => /[^A-Za-z0-9]/.test(p) },
];

export function PasswordRequirements({ password }: PasswordRequirementsProps) {
  if (!password) return null;

  return (
    <div className="mt-2 space-y-1" aria-label="密码要求">
      {RULES.map((rule) => {
        const ok = rule.check(password);
        return (
          <div key={rule.label} className="flex items-center gap-1.5">
            {ok ? (
              <Check className="h-3 w-3 shrink-0 text-[var(--status-ok-text)]" aria-hidden />
            ) : (
              <X className="h-3 w-3 shrink-0 text-[var(--auth-muted)]" aria-hidden />
            )}
            <span
              className={cn(
                "text-[0.7rem] leading-tight transition-colors",
                ok
                  ? "text-[var(--status-ok-text)]"
                  : "text-[var(--auth-muted)]",
              )}
            >
              {rule.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
