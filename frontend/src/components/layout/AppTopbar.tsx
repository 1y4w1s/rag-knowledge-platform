import type { ReactNode } from "react";

import { UserAvatarMenu } from "@/components/layout/UserAvatarMenu";
import { useAuth } from "@/lib/auth-context";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";

interface AppTopbarProps {
  breadcrumb: ReactNode;
  trailing?: ReactNode;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function AppTopbar({ breadcrumb, trailing, theme, onToggleTheme }: AppTopbarProps) {
  const { user } = useAuth();
  const { isOpen, toggle } = useMobileDrawer();

  return (
    <header className="app-topbar relative z-40 flex h-[52px] shrink-0 items-center gap-3 border-b border-[var(--shell-topbar-border)] bg-[var(--shell-glass)] px-6 text-sm shadow-[var(--shell-shadow)] backdrop-blur-xl after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-[linear-gradient(90deg,transparent,rgba(203,107,61,0.35),transparent)]">
      <button
        type="button"
        className="nav-toggle"
        onClick={toggle}
        aria-expanded={isOpen}
        aria-controls="app-sidebar"
        aria-label={isOpen ? "关闭导航" : "打开导航"}
      >
        <span className="nav-toggle-icon" aria-hidden="true" />
      </button>
      <div className="min-w-0 truncate text-muted [&_b]:font-medium [&_b]:text-foreground">
        {breadcrumb}
      </div>
      <div className="flex-1" />
      <button
        type="button"
        onClick={onToggleTheme}
        aria-label={theme === "dark" ? "切换到亮色" : "切换到暗色"}
        className="icon-btn flex h-9 w-9 items-center justify-center rounded-full border border-[var(--line2)] text-muted transition-colors hover:bg-[var(--nav-on)] hover:text-foreground"
      >
        {theme === "dark" ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]">
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]">
            <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
          </svg>
        )}
      </button>
      {trailing}
      {user && <UserAvatarMenu />}
    </header>
  );
}
