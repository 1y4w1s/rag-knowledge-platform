import type { ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AlertBannerProps {
  children: ReactNode;
  action?: ReactNode;
  className?: string;
  onDismiss?: () => void;
}

/** 暖色错态条 — 对齐 DESIGN-5 Banner 失败 token，非系统红 */
export function AlertBanner({
  children,
  action,
  className,
  onDismiss,
}: AlertBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "alert-warm-err flex flex-wrap items-center justify-between gap-3 rounded-[8px] border px-4 py-3 text-sm",
        className,
      )}
    >
      <span className="min-w-0 flex-1">{children}</span>
      <div className="flex shrink-0 items-center gap-2">
        {action}
        {onDismiss && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 border-[var(--status-err-border)] bg-white/80 px-2 text-[var(--status-err-text)] hover:bg-white"
            onClick={onDismiss}
            aria-label="关闭提示"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </Button>
        )}
      </div>
    </div>
  );
}
