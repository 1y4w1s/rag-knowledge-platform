import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SectionTitleProps {
  label: string;
  en?: string;
  count?: number;
  trailing?: ReactNode;
  /** quiet：减弱竖条/英文装饰（资料库列表等已安静页） */
  tone?: "default" | "quiet";
}

export function SectionTitle({
  label,
  en,
  count,
  trailing,
  tone = "default",
}: SectionTitleProps) {
  const quiet = tone === "quiet";

  return (
    <div
      className={cn(
        "mb-[14px] mt-[30px] flex items-baseline gap-2.5",
        quiet && "section-title-quiet",
      )}
    >
      <span
        className={cn(
          "relative font-[var(--serif)] font-semibold",
          quiet ? "text-[1.375rem] font-bold" : "pl-3.5 text-[17px]",
        )}
      >
        {!quiet ? (
          <span className="absolute left-0 top-1/2 h-[15px] w-[4px] -translate-y-1/2 rounded-[2px] bg-[var(--brand)]" />
        ) : null}
        {label}
      </span>
      {typeof count === "number" && (
        <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 font-mono text-[11px] font-semibold tabular-nums text-[var(--mut)]">
          {count}
        </span>
      )}
      {en && (
        <span
          className={cn(
            "text-[11px] uppercase tracking-[2px] text-[var(--mut)]",
            quiet && "tracking-[0.12em] opacity-45",
          )}
        >
          {en}
        </span>
      )}
      <span
        className={cn("h-px flex-1 bg-[var(--line2)]", quiet && "opacity-35")}
      />
      {trailing && <span className="self-center">{trailing}</span>}
    </div>
  );
}
