import { cn } from "@/lib/utils";

interface RegisterChoiceCardProps {
  selected: boolean;
  title: string;
  hint: string;
  onSelect: () => void;
}

/** 注册向导 · 个人/团队、创建者/成员 卡片（对齐 preview-register-workspace） */
export function RegisterChoiceCard({
  selected,
  title,
  hint,
  onSelect,
}: RegisterChoiceCardProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
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
          selected ? "border-[var(--auth-action)]" : "border-[var(--auth-line)]",
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
          {title}
        </span>
        <span className="mt-0.5 block text-xs leading-relaxed text-[var(--auth-muted)]">
          {hint}
        </span>
      </span>
    </button>
  );
}
