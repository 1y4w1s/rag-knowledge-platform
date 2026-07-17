import { Link } from "react-router-dom";

import { RuigeLogo } from "@/components/brand/RuigeLogo";
import { WorkspaceSwitcher } from "@/components/layout/WorkspaceSwitcher";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";

interface AppTopbarProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
  themeMode?: "light" | "dark" | "system";
}

/**
 * 顶栏（壳 v4 安静气质）
 * 结构：左 nav-toggle（仅移动端）+ Logo/字标；右工作区切换 + 主题
 * 不做：产品副标、底部分光条、重阴影
 */
export function AppTopbar({ theme, onToggleTheme, themeMode }: AppTopbarProps) {
  const { isOpen, toggle } = useMobileDrawer();

  return (
    <header className="app-topbar relative z-40 flex h-[56px] shrink-0 items-center gap-3 border-b border-[var(--shell-topbar-border)] bg-[var(--shell-glass)] px-5 text-sm backdrop-blur-[10px]">
      <button
        type="button"
        className="nav-toggle md:hidden"
        onClick={toggle}
        aria-expanded={isOpen}
        aria-controls="app-sidebar"
        aria-label={isOpen ? "关闭导航" : "打开导航"}
      >
        <span className="nav-toggle-icon" aria-hidden="true" />
      </button>

      <Link
        to="/dashboard"
        className="flex shrink-0 items-center gap-3 no-underline"
        aria-label="睿阁 · 概览"
      >
        <RuigeLogo size={34} />
        <span className="font-serif text-[20px] font-bold leading-none text-foreground">
          睿阁
        </span>
      </Link>

      <div className="flex-1" />

      <div className="topbar-right">
        <WorkspaceSwitcher compact />
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={
            themeMode === "dark"
              ? "切换到亮色"
              : themeMode === "system"
                ? "切换到暗色（当前跟随系统）"
                : "切换到跟随系统"
          }
          className="sun-icon"
        >
          {themeMode === "system" ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-4 w-4"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : theme === "dark" ? (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
}
