import { useCallback, useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";

type EffectiveTheme = "light" | "dark";

const THEME_KEY = "ruige-theme";

function getSavedTheme(): ThemeMode | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(THEME_KEY);
  if (v === "dark" || v === "light" || v === "system") return v;
  return null;
}

function getSystemTheme(): EffectiveTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function getInitialTheme(): ThemeMode {
  return getSavedTheme() ?? "system";
}

function resolveTheme(mode: ThemeMode): EffectiveTheme {
  return mode === "system" ? getSystemTheme() : mode;
}

/**
 * 全局主题 Hook：
 * - 支持亮色/暗色/跟随系统三种模式
 * - 初始化：localStorage > 默认 system
 * - system 模式下自动响应系统偏好变化
 * - 切换时优先使用 View Transitions API 平滑动画
 * - 主题记忆全站一致（登录页 + AppShell 共用）
 */
export function useTheme() {
  const [mode, setMode] = useState<ThemeMode>(getInitialTheme);
  const [effective, setEffective] = useState<EffectiveTheme>(() =>
    resolveTheme(getInitialTheme()),
  );

  /* 同步 effective 到 DOM + localStorage */
  useEffect(() => {
    document.documentElement.dataset.theme = effective;
    window.localStorage.setItem(THEME_KEY, mode);
  }, [effective, mode]);

  /* 系统偏好变化监听 */
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      if (mode === "system") {
        setEffective(e.matches ? "dark" : "light");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode]);

  const cycleTheme = useCallback(() => {
    const order: ThemeMode[] = ["light", "dark", "system"];
    const idx = order.indexOf(mode);
    const next = order[(idx + 1) % order.length];

    /* 优先使用 View Transitions API */
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => ViewTransition;
    };
    const apply = (m: ThemeMode) => {
      setMode(m);
      setEffective(resolveTheme(m));
    };
    if (doc.startViewTransition) {
      doc.startViewTransition(() => apply(next));
    } else {
      apply(next);
    }
  }, [mode]);

  const setTheme = useCallback((next: ThemeMode) => {
    setMode(next);
    setEffective(resolveTheme(next));
  }, []);

  return {
    mode,
    theme: effective,
    toggleTheme: cycleTheme,
    isSystem: mode === "system",
    setTheme,
    cycleTheme,
  };
}

/* View Transition 类型定义（TypeScript 标准库未包含） */
interface ViewTransition {
  finished: Promise<void>;
  ready: Promise<void>;
  updateCallbackDone: Promise<void>;
  skipTransition(): void;
}
