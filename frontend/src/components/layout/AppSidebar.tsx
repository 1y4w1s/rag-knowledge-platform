import {
  LayoutGrid,
  Library,
  MessageCircle,
  Building2,
  Users,
  Settings,
  ClipboardList,
  UserCircle,
} from "lucide-react";

import {
  SidebarNavItem,
  BrandMark,
  isChatNavActive,
  isKbNavActive,
} from "@/components/layout/sidebar-nav";

import { SidebarUserBlock } from "@/components/layout/UserAvatarMenu";

import { WorkspaceSwitcher } from "@/components/layout/WorkspaceSwitcher";
import { DepartmentPicker } from "@/components/sidebar/DepartmentPicker";

import { useAuth } from "@/lib/auth-context";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

export function AppSidebar() {
  const { user, isOrgAdmin } = useAuth();
  const { isOpen } = useMobileDrawer();
  const { isTeamWorkspace } = useWorkspace();

  const chatPath = "/ask";

  const showAdminNav = isTeamWorkspace && isOrgAdmin;

  const showMemberNav =
    isTeamWorkspace && Boolean(user?.org_id) && !isOrgAdmin;

  return (
    <aside
      id="app-sidebar"
      className={cn(
        "app-sidebar relative flex h-full w-sidebar shrink-0 flex-col overflow-y-auto border-r border-[var(--shell-border)] bg-[var(--shell-glass)] px-2.5 py-4 backdrop-blur-xl",
        isOpen && "open",
      )}
    >
      <div className="brand-row flex items-center gap-2.5 px-2.5 pb-3.5 mb-2 border-b border-border">
        <BrandMark />
        <span className="wordmark brand-text">睿阁</span>
      </div>

      <WorkspaceSwitcher />

      <DepartmentPicker />

      <div className="nav-label px-2.5 pb-1 pt-0.5 text-[0.62rem] font-semibold uppercase tracking-wide text-muted">
        导航
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 px-1">
        <SidebarNavItem to="/dashboard" end icon={<LayoutGrid className="h-[18px] w-[18px]" />}>
          概览
        </SidebarNavItem>

        <SidebarNavItem to="/knowledge-bases" match={isKbNavActive} icon={<Library className="h-[18px] w-[18px]" />}>
          资料库
        </SidebarNavItem>

        <SidebarNavItem to={chatPath} match={isChatNavActive} icon={<MessageCircle className="h-[18px] w-[18px]" />}>
          对话
        </SidebarNavItem>

        {showAdminNav ? (
          <>
            <SidebarNavItem to="/organization/departments" icon={<Building2 className="h-[18px] w-[18px]" />}>
              组织与部门
            </SidebarNavItem>

            <SidebarNavItem to="/organization/members" icon={<Users className="h-[18px] w-[18px]" />}>
              成员管理
            </SidebarNavItem>

            <SidebarNavItem to="/organization/settings" icon={<Settings className="h-[18px] w-[18px]" />}>
              团队设置
            </SidebarNavItem>

            <SidebarNavItem to="/admin/audit" icon={<ClipboardList className="h-[18px] w-[18px]" />}>
              操作审计
            </SidebarNavItem>
          </>
        ) : null}

        {showMemberNav ? (
          <SidebarNavItem to="/organization/members" icon={<Users className="h-[18px] w-[18px]" />}>
            团队成员
          </SidebarNavItem>
        ) : null}
      </nav>

      <div className="mt-2 border-t border-border px-1 pt-3">
        <SidebarNavItem to="/settings/account" icon={<UserCircle className="h-[18px] w-[18px]" />}>
          账号设置
        </SidebarNavItem>
        <SidebarUserBlock />
      </div>
    </aside>
  );
}

