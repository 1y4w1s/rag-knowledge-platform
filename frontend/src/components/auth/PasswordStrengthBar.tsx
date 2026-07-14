import { calcPasswordStrength } from "@/lib/password-strength";
import { cn } from "@/lib/utils";

interface PasswordStrengthBarProps {
  password: string;
}

const TONE_CLASS = {
  weak: "text-[color:var(--status-err-text)]",
  mid: "text-[color:var(--status-amber-text)]",
  strong: "text-[color:var(--status-ok-text)]",
} as const;

const FILL_CLASS = {
  weak: "bg-[color:var(--status-err)]",
  mid: "bg-[color:var(--status-amber)]",
  strong: "bg-[color:var(--status-ok)]",
} as const;

export function PasswordStrengthBar({ password }: PasswordStrengthBarProps) {
  const { level, label, tone } = calcPasswordStrength(password);
  if (!password) return null;

  return (
    <div className="mt-2" aria-live="polite">
      <div
        className="flex gap-1"
        role="meter"
        aria-valuenow={level}
        aria-valuemin={0}
        aria-valuemax={3}
        aria-label="密码强度"
      >
        {[1, 2, 3].map((segment) => (
          <span
            key={segment}
            className={cn(
              "h-1 flex-1 rounded-full bg-[color:var(--line2)] transition-colors",
              level >= segment && tone && FILL_CLASS[tone],
            )}
          />
        ))}
      </div>
      {label && tone && (
        <p className={cn("mt-1.5 text-[0.7rem]", TONE_CLASS[tone])}>{label}</p>
      )}
    </div>
  );
}
