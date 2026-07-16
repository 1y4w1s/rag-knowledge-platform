import type { ReactNode } from "react";

interface SectionTitleProps {
  label: string;
  en?: string;
  count?: number;
  trailing?: ReactNode;
}

export function SectionTitle({ label, en, count, trailing }: SectionTitleProps) {
  return (
    <div className="flex items-baseline gap-2.5 mt-[30px] mb-[14px]">
      <span className="relative pl-3.5 font-[var(--serif)] text-[17px] font-semibold">
        {label}
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-[15px] w-[4px] rounded-[2px] bg-[var(--brand)]" />
      </span>
      {typeof count === "number" && (
        <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[11px] font-mono font-semibold text-[var(--mut)] tabular-nums">
          {count}
        </span>
      )}
      {en && (
        <span className="text-[11px] tracking-[2px] uppercase text-[var(--mut)]">
          {en}
        </span>
      )}
      <span className="flex-1 h-px bg-[var(--line2)]" />
      {trailing && (
        <span className="self-center">{trailing}</span>
      )}
    </div>
  );
}
