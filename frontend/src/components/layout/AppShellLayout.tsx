import { useEffect } from "react";
import { Outlet, useLocation, useMatches } from "react-router-dom";

import { AppSidebar } from "@/components/layout/AppSidebar";
import { AppTopbar } from "@/components/layout/AppTopbar";
import { UnassignedDepartmentBanner } from "@/components/organization/UnassignedDepartmentBanner";
import { useAuth } from "@/lib/auth-context";
import {
  MobileDrawerProvider,
  useMobileDrawer,
} from "@/lib/mobile-drawer-context";
import { shouldShowUnassignedBanner } from "@/lib/org-permissions";
import { ShellBreadcrumbProvider, useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";
import { useTheme } from "@/lib/use-theme";
import { cn } from "@/lib/utils";

export interface ShellRouteHandle {
  breadcrumb: React.ReactNode;
  trailing?: React.ReactNode;
}

/** 已有 SectionTitle / h2 自带标题区的路由前缀 —— 这些页不再显示面包屑，避免与页面标题重复 */
const HIDE_BREADCRUMB_PREFIXES = [
  "/knowledge-bases",
  "/settings",
  "/organization",
  "/admin",
  "/chat",
  "/ask",
];

function AppShellContent() {
  const matches = useMatches();
  const location = useLocation();
  const { user } = useAuth();
  const { workspace } = useWorkspace();
  const { departmentId } = useDepartment();
  const { override } = useShellBreadcrumb();
  const { isOpen, close } = useMobileDrawer();
  const showUnassignedBanner = shouldShowUnassignedBanner(user, workspace);
  const handle = [...matches].reverse().find((m) => m.handle)?.handle as
    | ShellRouteHandle
    | undefined;

  const { theme, toggleTheme } = useTheme();
  const hideBreadcrumb =
    location.pathname === "/dashboard" ||
    HIDE_BREADCRUMB_PREFIXES.some((p) => location.pathname.startsWith(p));

  useEffect(() => {
    close();
  }, [location.pathname, workspace, departmentId, close]);

  return (
    <div className="app-shell flex h-screen overflow-hidden" data-theme={theme}>
      <a href="#main" className="skip-link">
        跳到主内容
      </a>
      <div className="app-aurora" aria-hidden="true" />
      <div className="app-grain" aria-hidden="true" />
      <div
        className={cn("drawer-backdrop", isOpen && "open")}
        aria-hidden={!isOpen}
        onClick={close}
      />
      <AppSidebar />
      <div className="relative z-[1] flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <AppTopbar
          theme={theme}
          onToggleTheme={toggleTheme}
        />
        {/* 面包屑 + trailing：预览顶栏里没有这些元素，单独一行渲染在顶栏与内容之间。已有 SectionTitle/h2 的页面（黑名单）不显示，避免双标题 */}
        {!hideBreadcrumb && (override ?? handle?.breadcrumb ?? handle?.trailing) && (
          <div className="flex shrink-0 items-center gap-2 border-b border-[var(--line2)] bg-[var(--shell-glass)]/60 px-5 py-2 text-sm text-muted">
            <span className="truncate">
              <span className="mx-1 text-[var(--line2)]">/</span>
              {override ?? handle?.breadcrumb ?? <>睿阁</>}
            </span>
            <div className="flex-1" />
            {handle?.trailing}
          </div>
        )}
        <main id="main" tabIndex={-1} className="min-h-0 flex-1 overflow-auto p-6">
          {showUnassignedBanner && <UnassignedDepartmentBanner />}
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function AppShellLayout() {
  return (
    <ShellBreadcrumbProvider>
      <MobileDrawerProvider>
        <AppShellContent />
      </MobileDrawerProvider>
    </ShellBreadcrumbProvider>
  );
}
