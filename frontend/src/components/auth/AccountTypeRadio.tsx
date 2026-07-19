import { cn } from "@/lib/utils";
import type { AccountType } from "@/lib/auth-storage";

interface AccountTypeRadioProps {
  value: AccountType;
  onChange: (value: AccountType) => void;
}

const OPTIONS: { value: AccountType; label: string; hint: string }[] = [
  { value: "personal", label: "个人账号", hint: "单人使用，自建资料库" },
  {
    value: "enterprise",
    label: "团队账号",
    hint: "创建团队，可邀请成员（管理员上传文档）",
  },
];

export function AccountTypeRadio({ value, onChange }: AccountTypeRadioProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-1.5 block text-xs font-medium text-[var(--auth-muted)]">
        账号类型
      </legend>
      <div className="grid gap-2.5">
        {OPTIONS.map((opt) => {
          const selected = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(opt.value)}
              className={cn(
                "flex w-full cursor-pointer gap-3 rounded-xl border-[1.5px] px-4 py-3.5 text-left transition-all duration-200",
                selected
                  ? "scale-[1.01] border-[var(--auth-action)] bg-[var(--auth-selected)] shadow-[0_0_0_1px_rgb(203_107_61/0.12)]"
                  : "border-[var(--auth-line)] bg-[var(--auth-card)] hover:scale-[1.01] hover:border-[color:rgb(203_107_61/0.35)] hover:shadow-[var(--auth-shadow)]",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                  selected
                    ? "border-[var(--auth-action)]"
                    : "border-[var(--auth-line)]",
                )}
                aria-hidden
              >
                <span
                  className={cn(
                    "h-2 w-2 rounded-full transition-colors",
                    selected ? "bg-[var(--auth-action)]" : "bg-transparent",
                  )}
                />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-[var(--auth-text)]">
                  {opt.label}
                </span>
                <span className="mt-0.5 block text-xs leading-relaxed text-[var(--auth-muted)]">
                  {opt.hint}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
