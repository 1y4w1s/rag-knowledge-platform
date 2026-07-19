import { RegisterChoiceCard } from "@/components/auth/RegisterChoiceCard";
import type { RegisterUsage } from "@/components/auth/register-form-types";
import { Button } from "@/components/ui/button";

interface RegisterUsageStepProps {
  usage: RegisterUsage | null;
  onSelectUsage: (usage: RegisterUsage) => void;
  onContinue: () => void;
}

export function RegisterUsageStep({
  usage,
  onSelectUsage,
  onContinue,
}: RegisterUsageStepProps) {
  return (
    <>
      <div className="mb-3 shrink-0">
        <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
          你打算怎么用？
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--auth-muted)]">
          个人仅使用我的空间；团队将创建或加入团队空间（与我的空间并存）。
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-2.5" role="radiogroup" aria-label="注册用法">
        <RegisterChoiceCard
          selected={usage === "personal"}
          title="个人"
          hint="单人使用，资料库在「我的空间」"
          onSelect={() => onSelectUsage("personal")}
        />
        <RegisterChoiceCard
          selected={usage === "team"}
          title="团队"
          hint="创建团队或凭邀请码加入；仍可切换回我的空间"
          onSelect={() => onSelectUsage("team")}
        />
      </div>

      {!usage && (
        <p className="mt-3 text-center text-xs text-[var(--auth-muted)]">
          请选择个人或团队以继续
        </p>
      )}

      <div className="mt-auto shrink-0 pt-4">
        <Button
          type="button"
          variant="auth"
          className="w-full"
          disabled={!usage}
          onClick={onContinue}
        >
          继续
        </Button>
      </div>
    </>
  );
}
