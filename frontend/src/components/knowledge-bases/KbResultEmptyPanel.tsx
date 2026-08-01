import { useId, type ReactNode } from "react";
import { Link } from "react-router-dom";

export interface SearchSuggestionItem {
  label: string;
  /** 用 React Router Link 导航至此路径 */
  to?: string;
  /** 或用回调触发搜索 */
  onClick?: () => void;
}

interface KbResultEmptyPanelProps {
  title: string;
  description: string;
  /** 清除搜索/筛选等 CTA */
  action?: ReactNode;
  /** 筛选/搜索切换时屏幕阅读器播报 */
  live?: boolean;
  /** 推荐搜索关键词标签 */
  suggestions?: SearchSuggestionItem[];
}

/** Plan-11/2B+2D · 搜索/筛选无结果共用虚线卡片壳 */
export function KbResultEmptyPanel({
  title,
  description,
  action,
  live = false,
  suggestions,
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
      {suggestions && suggestions.length > 0 && (
        <div className="kb-result-empty-suggestions">
          <span className="kb-suggestion-label">试试这些关键词：</span>
          <div className="kb-suggestion-tags">
            {suggestions.map((item) =>
              item.to ? (
                <Link
                  key={item.label}
                  to={item.to}
                  className="kb-suggestion-tag"
                >
                  {item.label}
                </Link>
              ) : (
                <button
                  key={item.label}
                  type="button"
                  className="kb-suggestion-tag"
                  onClick={item.onClick}
                >
                  {item.label}
                </button>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
