import { useId, type ReactNode } from "react";

interface KbResultEmptyPanelProps {
  title: string;
  description: string;
  /** 清除搜索/筛选等 CTA */
  action?: ReactNode;
  /** 筛选/搜索切换时屏幕阅读器播报 */
  live?: boolean;
}

/** Plan-11/2B+2D · 搜索/筛选无结果共用虚线卡片壳 */
export function KbResultEmptyPanel({
  title,
  description,
  action,
  live = false,
}: KbResultEmptyPanelProps) {
  const titleId = useId();
  const descId = useId();

  return (
    <div
      className="kb-result-empty"
      role="region"
      aria-labelledby={titleId}
      aria-describedby={descId}
      {...(live ? { "aria-live": "polite" as const } : {})}
    >
      <p id={titleId} className="kb-result-empty-title">
        {title}
      </p>
      <p id={descId} className="kb-result-empty-desc">
        {description}
      </p>
      {action && <div className="kb-result-empty-action">{action}</div>}
    </div>
  );
}
