import { useEffect, useRef, type ReactNode } from "react";

type RevealVariant = "up" | "scale" | "left" | "none";

interface RevealProps {
  variant?: RevealVariant;
  /** 错峰延迟（毫秒） */
  delay?: number;
  className?: string;
  children: ReactNode;
}

/**
 * 滚动入场包裹器：进入视口时由 IntersectionObserver 加 `.in-view` 触发 CSS 过渡。
 * 尊重 prefers-reduced-motion：直接显示，不做位移/透明度动画。
 */
export function Reveal({
  variant = "up",
  delay = 0,
  className = "",
  children,
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      el.classList.add("in-view");
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const variantClass = variant === "none" ? "" : `reveal-${variant}`;
  const style = delay
    ? ({ ["--rv-delay" as string]: `${delay}ms` } as React.CSSProperties)
    : undefined;

  return (
    <div
      ref={ref}
      className={`reveal ${variantClass} ${className}`.trim()}
      style={style}
    >
      {children}
    </div>
  );
}
