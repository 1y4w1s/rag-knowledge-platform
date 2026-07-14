import type { ReactNode } from "react";

import { UserAvatarMenu } from "@/components/layout/UserAvatarMenu";
import { useAuth } from "@/lib/auth-context";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";

interface AppTopbarProps {
  breadcrumb: ReactNode;
  trailing?: ReactNode;
}

export function AppTopbar({ breadcrumb, trailing }: AppTopbarProps) {
  const { user } = useAuth();
  const { isOpen, toggle } = useMobileDrawer();

  return (
    <header className="app-topbar relative z-40 flex h-[52px] shrink-0 items-center gap-3 border-b border-[rgba(232,196,176,0.5)] bg-white/70 px-6 text-sm shadow-[0_1px_0_rgba(255,255,255,0.7),0_1px_14px_rgba(120,70,45,0.07)] backdrop-blur-xl after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-[linear-gradient(90deg,transparent,rgba(203,107,61,0.35),transparent)]">
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
      {trailing}
      {user && <UserAvatarMenu />}
    </header>
  );
}
