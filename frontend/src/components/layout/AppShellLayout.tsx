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
import { cn } from "@/lib/utils";

export interface ShellRouteHandle {
  breadcrumb: React.ReactNode;
  trailing?: React.ReactNode;
}

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

  useEffect(() => {
    close();
  }, [location.pathname, workspace, departmentId, close]);

  return (
    <div className="app-shell flex h-screen overflow-hidden">
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
          breadcrumb={override ?? handle?.breadcrumb ?? <>睿阁</>}
          trailing={handle?.trailing}
        />
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
