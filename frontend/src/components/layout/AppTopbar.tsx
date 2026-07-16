import { Link, useLocation } from "react-router-dom";

import { RuigeLogo } from "@/components/brand/RuigeLogo";
import { WorkspaceSwitcher } from "@/components/layout/WorkspaceSwitcher";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";

interface AppTopbarProps {
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

/**
 * 顶栏（100% 对齐预览 dashboard-bold-preview.html · topbar）
 * 结构：左 nav-toggle（仅移动端） + 品牌；右 scope chip + pill 三按钮组 + 极简 sun 图标
 */
export function AppTopbar({ theme, onToggleTheme }: AppTopbarProps) {
  const { isOpen, toggle } = useMobileDrawer();
  const { pathname } = useLocation();

  return (
    <header className="app-topbar relative z-40 flex h-[56px] shrink-0 items-center gap-3 border-b border-[var(--shell-topbar-border)] bg-[var(--shell-glass)] px-5 text-sm shadow-[var(--shell-shadow)] backdrop-blur-xl after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-[linear-gradient(90deg,transparent,rgba(203,107,61,0.35),transparent)]">
      {/* 移动端导航开合（桌面隐藏） */}
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

      {/* 品牌（链接回概览） */}
      <Link to="/dashboard" className="flex shrink-0 items-center gap-[13px] no-underline">
        <RuigeLogo size={34} />
        <span className="leading-none">
          <span className="block font-[var(--serif)] text-[22px] font-semibold tracking-[0.5px] text-foreground">
            睿阁
          </span>
          <span className="mt-[1px] block text-[12px] text-[var(--mut)]">
            企业知识工作台
          </span>
        </span>
      </Link>

      {/* 面包屑（dashboard 页不显示，预览无面包屑；其他页由 AppShellLayout 渲染在下方） */}
      {pathname !== "/dashboard" ? null : null}

      <div className="flex-1" />

      {/* 顶栏右侧控制区 */}
      <div className="topbar-right">
        <WorkspaceSwitcher compact />
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "切换到亮色" : "切换到暗色"}
          className="sun-icon"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" />
          </svg>
        </button>
      </div>
    </header>
  );
}
