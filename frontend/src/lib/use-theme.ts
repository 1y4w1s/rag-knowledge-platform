import { useCallback, useEffect, useRef, useState } from "react";

export type ThemeMode = "light" | "dark";

const THEME_KEY = "ruige-theme";

function getSavedTheme(): ThemeMode | null {
  if (typeof window === "undefined") return null;
  const v = window.localStorage.getItem(THEME_KEY);
  return v === "dark" || v === "light" ? v : null;
}

function getSystemTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function getInitialTheme(): ThemeMode {
  return getSavedTheme() ?? getSystemTheme();
}

/**
 * 全局主题 Hook：
 * - 初始化：localStorage > 系统偏好（prefers-color-scheme）
 * - 系统偏好变化时自动响应（若用户未手动覆盖）
 * - 切换时优先使用 View Transitions API 平滑动画，fallback 到直接切换
 * - 主题记忆全站一致（登录页 + AppShell 共用）
 */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(getInitialTheme);
  const userOverridden = useRef<boolean>(getSavedTheme() !== null);

  /* 同步到 DOM + localStorage */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  /* 系统偏好变化监听（仅当用户未手动选择时） */
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      if (userOverridden.current) return; /* 用户已手动选择，不跟随系统 */
      const next = e.matches ? "dark" : "light";
      setThemeState(next);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const setTheme = useCallback((next: ThemeMode) => {
    userOverridden.current = true;
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    userOverridden.current = true;
    const next = theme === "dark" ? "light" : "dark";

    /* 优先使用 View Transitions API 实现平滑主题切换 */
    const doc = document as Document & { startViewTransition?: (cb: () => void) => ViewTransition };
    if (doc.startViewTransition) {
      doc.startViewTransition(() => setThemeState(next));
    } else {
      setThemeState(next);
    }
  }, [theme]);

  return { theme, setTheme, toggleTheme };
}

/* View Transition 类型定义（TypeScript 标准库未包含） */
interface ViewTransition {
  finished: Promise<void>;
  ready: Promise<void>;
  updateCallbackDone: Promise<void>;
  skipTransition(): void;
}
