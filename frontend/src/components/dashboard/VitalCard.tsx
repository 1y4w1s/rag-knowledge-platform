import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { CountUp } from "@/components/common/CountUp";

type Accent = "brand" | "ok" | "info";

const ACCENT_MAP: Record<Accent, string> = {
  brand: "var(--brand)",
  ok: "var(--ok)",
  info: "var(--info)",
};

interface VitalCardProps {
  value: number | string;
  label: string;
  hint?: string;
  accent?: Accent;
  href?: string;
  className?: string;
}

export function VitalCard({
  value,
  label,
  hint,
  accent = "brand",
  href,
  className,
}: VitalCardProps) {
  const accentVar = ACCENT_MAP[accent];

  const body = (
    <div
        className={cn(
          "group relative flex-1 min-w-[150px] overflow-hidden rounded-2xl border border-[var(--line2)] bg-[var(--surf)] pt-[18px] pr-[22px] pb-[15px] pl-[22px] transition-all duration-[350ms]",
        "shadow-[var(--top-hi),var(--card-shadow)]",
        "hover:-translate-y-0.5 hover:border-[var(--line)] hover:shadow-[var(--top-hi),var(--card-shadow-lift)]",
        className,
      )}
      style={{ ["--vital-accent" as string]: accentVar }}
    >
      {/* 左侧语义色带 */}
      <span
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-r-[3px] z-[1]"
        style={{ background: `linear-gradient(var(--vital-accent), var(--brand-deep))` }}
        aria-hidden
      />
      {/* 微色调覆盖 — 预览值 4% → hover 8% */}
      <span
        className="absolute inset-0 opacity-[0.04] pointer-events-none z-0 transition-opacity group-hover:opacity-[0.08]"
        style={{ background: `var(--vital-accent)` }}
        aria-hidden
      />
      <div className="relative z-[1]">
        {/* 数字 — 预览 font-weight: 700 (bold)，不是 600 (semibold) */}
        <div className="font-[var(--serif)] text-[32px] font-bold leading-none tabular-nums">
          {typeof value === "number" ? <CountUp value={value} /> : value}
        </div>
        <div className="mt-2 text-xs text-[var(--mut)]">{label}</div>
        {hint && (
          <div className="mt-1 text-xs text-[var(--mut)]">{hint}</div>
        )}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="flex-1 no-underline">
        {body}
      </Link>
    );
  }

  return body;
}
