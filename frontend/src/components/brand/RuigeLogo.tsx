import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

interface RuigeLogoProps {
  /** 标记高度（px）。字标字号按此比例自适应。默认 28。 */
  size?: number;
  /** 是否在标记右侧显示「睿阁」字标。默认 false（仅标记）。 */
  withWordmark?: boolean;
  className?: string;
  style?: CSSProperties;
  /** 无障碍标签。默认「睿阁」。 */
  title?: string;
}

/**
 * 睿阁品牌标记：层叠飞檐塔阁（藏书阁意象）。
 * - 标记使用 currentColor，由容器文字色驱动；此处固定为品牌赤陶 --action。
 * - 字标为暖褐/前景深色，与赤陶标记形成经典 lockup。
 * - 表单规则：飞檐两端统一上翘（几何宪法）；三段层叠=视觉重量+「多文档入库」；
 *   基座拱门负空间=第二眼才见的「知识之门 / 检索入口」。
 */
export function RuigeLogo({
  size = 28,
  withWordmark = false,
  className,
  style,
  title = "睿阁",
}: RuigeLogoProps) {
  return (
    <span
      className={cn("inline-flex items-center gap-2", className)}
      style={style}
      role="img"
      aria-label={title}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        aria-hidden
        className="block shrink-0"
        style={{ color: "var(--action)" }}
      >
        {/* 宝顶 */}
        <path d="M24 4 L27 9 L21 9 Z" fill="currentColor" />
        {/* 顶层飞檐 */}
        <path
          d="M15.5 14.5 Q24 11.5 32.5 14.5"
          stroke="currentColor"
          strokeWidth={3}
          strokeLinecap="round"
        />
        <path
          d="M15.5 14.5 l-2 -2 M32.5 14.5 l2 -2"
          stroke="currentColor"
          strokeWidth={3}
          strokeLinecap="round"
        />
        {/* 顶层立柱（书脊意象） */}
        <line
          x1={20}
          y1={15.5}
          x2={20}
          y2={22.5}
          stroke="currentColor"
          strokeWidth={2.6}
          strokeLinecap="round"
        />
        <line
          x1={28}
          y1={15.5}
          x2={28}
          y2={22.5}
          stroke="currentColor"
          strokeWidth={2.6}
          strokeLinecap="round"
        />
        {/* 中层飞檐 */}
        <path
          d="M12.5 24 Q24 21 35.5 24"
          stroke="currentColor"
          strokeWidth={3}
          strokeLinecap="round"
        />
        <path
          d="M12.5 24 l-2.5 -2.2 M35.5 24 l2.5 -2.2"
          stroke="currentColor"
          strokeWidth={3}
          strokeLinecap="round"
        />
        {/* 基座 + 拱门负空间（evenodd 挖空） */}
        <path
          d="M14 25.5 L34 25.5 L37 40 L11 40 Z M20.5 40 L20.5 33 Q24 30 27.5 33 L27.5 40 Z"
          fill="currentColor"
          fillRule="evenodd"
        />
      </svg>
      {withWordmark && (
        <span
          className="brand-text font-serif font-bold leading-none tracking-[0.04em] text-foreground"
          style={{ fontSize: size * 0.62 }}
        >
          睿阁
        </span>
      )}
    </span>
  );
}
