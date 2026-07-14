import { cn } from "@/lib/utils";

export type AuthTab = "login" | "register";

const TAB_LABELS: { id: AuthTab; label: string }[] = [
  { id: "login", label: "登录" },
  { id: "register", label: "注册" },
];

interface AuthSegmentedTabsProps {
  active: AuthTab;
  onChange: (tab: AuthTab) => void;
}

export function AuthSegmentedTabs({ active, onChange }: AuthSegmentedTabsProps) {
  return (
    <div
      className="mb-5 flex gap-1 rounded-[10px] bg-[var(--auth-tab-bg)] p-1"
      role="tablist"
      aria-label="认证方式"
    >
      {TAB_LABELS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={active === id}
          onClick={() => onChange(id)}
          className={cn(
            "flex-1 rounded-sm px-2 py-2 text-[0.82rem] transition-colors",
            active === id
              ? "bg-[var(--auth-card)] font-semibold text-[var(--auth-text)] shadow-sm"
              : "text-[var(--auth-muted)] hover:text-[var(--auth-text)]",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
