import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { CountUp } from "@/components/common/CountUp";

type Accent = "brand" | "ok" | "info";

const ACCENT_MAP: Record<Accent, string> = {
  brand: "var(--action)",
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
      className={cn("dash-vital group", className)}
      style={{ ["--vital-accent" as string]: accentVar }}
    >
      <span className="dash-vital-bar" aria-hidden />
      <div className="relative z-[1]">
        <div className="font-[var(--serif)] text-[1.875rem] font-bold leading-none tracking-tight tabular-nums">
          {typeof value === "number" ? <CountUp value={value} /> : value}
        </div>
        <div className="mt-2 text-xs font-semibold text-foreground">{label}</div>
        {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link to={href} className="block no-underline">
        {body}
      </Link>
    );
  }

  return body;
}
