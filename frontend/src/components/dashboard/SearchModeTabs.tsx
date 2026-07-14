import { cn } from "@/lib/utils";
import type { SearchMode } from "@/lib/search-api";

const TAB_LABELS: { id: SearchMode; label: string }[] = [
  { id: "filename", label: "文件名" },
  { id: "content", label: "正文" },
];

interface SearchModeTabsProps {
  active: SearchMode;
  onChange: (mode: SearchMode) => void;
}

export function SearchModeTabs({ active, onChange }: SearchModeTabsProps) {
  return (
    <div
      className="mb-3 inline-flex flex-nowrap items-start gap-2"
      role="tablist"
      aria-label="搜索范围"
    >
      {TAB_LABELS.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={active === id}
          onClick={() => onChange(id)}
          className={cn(
            "flex-shrink-0 whitespace-nowrap rounded-[10px] border px-3.5 py-1.5 text-[0.82rem] font-medium transition-colors",
            active === id
              ? "border-[var(--action)] bg-[var(--action)] text-white shadow-sm"
              : "border-border bg-white text-[var(--mut)] hover:border-[#E8C4B0] hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
