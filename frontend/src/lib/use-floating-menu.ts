/**
 * useFloatingMenu — 通用浮动菜单定位 hook
 *
 * 绕过父级 overflow 限制，通过 createPortal 将菜单渲染到 document.body。
 * 自动检测视口边界并翻转方向。
 *
 * 用法：
 *   const { floatingRef, style } = useFloatingMenu(anchorRef, open);
 *   return createPortal(<div ref={floatingRef} style={style}>...</div>, document.body);
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface FloatingStyle {
  position: "fixed";
  left: number;
  top: number;
}

interface UseFloatingMenuResult {
  /** 挂到菜单根元素的 ref，用于 click-outside 检测 */
  floatingRef: React.RefObject<HTMLDivElement | null>;
  /** 注入到菜单元素的 style */
  style: FloatingStyle;
}

export function useFloatingMenu(
  anchorRef: React.RefObject<HTMLElement | null>,
  open: boolean,
  options?: { offset?: number; flip?: boolean },
): UseFloatingMenuResult {
  const floatingRef = useRef<HTMLDivElement | null>(null);
  const offset = options?.offset ?? 8;
  const flip = options?.flip ?? true;

  const calc = useCallback((): FloatingStyle => {
    const anchor = anchorRef.current;
    if (!anchor) return { position: "fixed", left: -9999, top: -9999 };

    const rect = anchor.getBoundingClientRect();
    const menuWidth = 200; // will be updated after render

    // 默认：从锚点右下角展开
    let left = rect.right + offset;
    let top = rect.top;

    // 视口右侧空间不足 → 向左展开
    if (flip && left + menuWidth > window.innerWidth) {
      left = rect.left - offset;
      // 如果左边也不够 → 保持原位置
    }

    // 视口底部空间不足 → 向上展开
    if (flip && top + 120 > window.innerHeight) {
      top = rect.bottom - 120;
    }

    return { position: "fixed", left, top };
  }, [anchorRef, offset, flip]);

  const [style, setStyle] = useState<FloatingStyle>(() =>
    open ? calc() : { position: "fixed", left: -9999, top: -9999 },
  );

  useEffect(() => {
    if (!open) {
      setStyle({ position: "fixed", left: -9999, top: -9999 });
      return;
    }

    setStyle(calc());

    // 更新菜单实际宽度后的二次校准
    const raf = requestAnimationFrame(() => {
      if (!floatingRef.current) return;
      const menuRect = floatingRef.current.getBoundingClientRect();
      const anchor = anchorRef.current;
      if (!anchor) return;
      const anchorRect = anchor.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;

      let left = anchorRect.right + offset;
      let top = anchorRect.top;

      // 右侧空间不足 → 向左展开
      if (flip && left + menuRect.width > vw) {
        left = anchorRect.left - offset - menuRect.width;
      }

      // 底部空间不足 → 向上展开
      if (flip && top + menuRect.height > vh) {
        top = vh - menuRect.height - offset;
      }

      // 如果上展开会超出顶部 → 回退到底部
      if (top < 4) {
        top = anchorRect.bottom + offset;
      }

      setStyle({ position: "fixed", left: Math.max(4, left), top: Math.max(4, top) });
    });

    return () => cancelAnimationFrame(raf);
  }, [open, calc, anchorRef, offset, flip]);

  // 侧栏滚动 / resize 时重新定位
  useEffect(() => {
    if (!open) return;
    function onUpdate() {
      if (open) setStyle(calc());
    }
    window.addEventListener("scroll", onUpdate, true);
    window.addEventListener("resize", onUpdate);
    return () => {
      window.removeEventListener("scroll", onUpdate, true);
      window.removeEventListener("resize", onUpdate);
    };
  }, [open, calc]);

  return { floatingRef, style };
}
