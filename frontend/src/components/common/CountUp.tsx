import { useEffect, useState } from "react";

interface CountUpProps {
  value: number;
  duration?: number;
  className?: string;
}

/**
 * KPI 数字滚动递增：进入视图后从 0 缓动到目标值（easeOutCubic）。
 * 尊重 prefers-reduced-motion：直接显示终值。
 */
export function CountUp({ value, duration = 1100, className }: CountUpProps) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) {
      setDisplay(value);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(value * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return (
    <span className={className}>{display.toLocaleString("zh-CN")}</span>
  );
}
