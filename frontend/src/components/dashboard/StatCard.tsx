import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import { CountUp } from "@/components/common/CountUp";

export type IconTone = "clay" | "blue" | "green" | "rose" | "slate";

const TONE_STYLES: Record<IconTone, { bg: string; icon: string; ring: string }> = {
  clay: {
    bg: "bg-[#FFF1EA]",
    icon: "text-[#B86A3D]",
    ring: "ring-[#E8C4B0]/40",
  },
  blue: {
    bg: "bg-[#EDF4FF]",
    icon: "text-[#3B6FCF]",
    ring: "ring-[#A7C4F1]/40",
  },
  green: {
    bg: "bg-[#F0F9F3]",
    icon: "text-[#3D8F63]",
    ring: "ring-[#B8E0C8]/40",
  },
  rose: {
    bg: "bg-[#FDF2F4]",
    icon: "text-[#C95B6E]",
    ring: "ring-[#F0C4CB]/40",
  },
  slate: {
    bg: "bg-[#F5F5F4]",
    icon: "text-[#52525B]",
    ring: "ring-[#E5E5E5]/40",
  },
};

interface StatCardFooterLink {
  label: string;
  href: string;
}

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value?: string | number;
  hint?: string;
  inline?: ReactNode;
  dim?: boolean;
  href?: string;
  footerLinks?: StatCardFooterLink[];
  iconTone?: IconTone;
  /** 错峰入场序号（v6 动效）；不传则不启用入场动画 */
  index?: number;
}

function StatCardMain({
  icon: Icon,
  label,
  value,
  hint,
  inline,
  showHint,
  iconTone = "slate",
}: Pick<
  StatCardProps,
  "icon" | "label" | "value" | "hint" | "inline" | "iconTone"
> & { showHint: boolean }) {
  const tone = TONE_STYLES[iconTone];
  return (
    <>
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] ring-1 ring-inset",
          tone.bg,
          tone.ring,
        )}
        aria-hidden
      >
        <Icon className={cn("h-[18px] w-[18px]", tone.icon)} strokeWidth={1.5} />
      </span>
      <div className="min-w-0 flex-1">
        {inline ?? (
          <p
            className={cn(
              "font-mono text-[1.35rem] font-semibold leading-none tracking-[0.05em] tabular-nums",
              tone.icon,
            )}
          >
            {typeof value === "number" ? <CountUp value={value} /> : value}
          </p>
        )}
        <p className="mt-1 text-[0.8125rem] font-medium text-foreground">
          {label}
        </p>
        {showHint && hint && (
          <p className="mt-0.5 text-[0.65rem] text-muted">{hint}</p>
        )}
      </div>
    </>
  );
}

export function StatCard({
  icon,
  label,
  value,
  hint,
  inline,
  dim,
  href,
  footerLinks,
  iconTone = "slate",
  index,
}: StatCardProps) {
  const hasFooterLinks = Boolean(footerLinks?.length);
  const cardClass = cn(
    "card-lift relative flex min-h-[92px] flex-col rounded-xl border border-border bg-white/[0.85] px-3.5 py-3 shadow-sm transition-all duration-200",
    "hover:border-[rgba(203,107,61,0.28)]",
    index !== undefined && "v6-rise",
    dim && "opacity-[0.55]",
    href &&
      "hover:border-[rgba(203,107,61,0.4)] hover:bg-white hover:shadow-[var(--shadow-xl),0_0_0_1px_rgba(203,107,61,0.2)] focus-within:border-[rgba(203,107,61,0.4)] focus-within:ring-2 focus-within:ring-[rgba(203,107,61,0.12)]",
  );
  const rowClass = "flex flex-1 items-center gap-2.5";

  return (
    <div
      className={cardClass}
      style={index !== undefined ? ({ ["--v6-i" as string]: index } as React.CSSProperties) : undefined}
    >
      <span className="card-top-accent" aria-hidden />
      {href ? (
        <Link to={href} className={cn(rowClass, "no-underline")}>
          <StatCardMain
            icon={icon}
            label={label}
            value={value}
            hint={hint}
            inline={inline}
            iconTone={iconTone}
            showHint={!hasFooterLinks}
          />
        </Link>
      ) : (
        <div className={rowClass}>
          <StatCardMain
            icon={icon}
            label={label}
            value={value}
            hint={hint}
            inline={inline}
            iconTone={iconTone}
            showHint={!hasFooterLinks}
          />
        </div>
      )}
      {hasFooterLinks && (
        <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 pl-[30px]">
          {footerLinks!.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className="text-[0.65rem] font-medium text-[var(--action)] underline-offset-2 hover:underline"
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

interface StatCardSkeletonProps {
  label: string;
}

export function StatCardSkeleton({ label }: StatCardSkeletonProps) {
  return (
    <div className="flex h-[92px] items-center gap-2.5 rounded-xl border border-border bg-white/[0.85] px-3.5 shadow-sm">
      <div className="h-9 w-9 shrink-0 rounded-[10px] bg-border/80" />
      <div>
        <div className="h-7 w-12 rounded bg-border/80" />
        <p className="mt-2.5 text-xs text-muted">{label}</p>
      </div>
    </div>
  );
}
