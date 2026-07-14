import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
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

import { RuigeLogo } from "@/components/brand/RuigeLogo";
import {
  isChatNavActive,
  isKbNavActive,
} from "@/components/layout/sidebar-nav";

import { WorkspaceSwitcher } from "@/components/layout/WorkspaceSwitcher";
import { DepartmentPicker } from "@/components/sidebar/DepartmentPicker";
import { UserAvatarMenu } from "@/components/layout/UserAvatarMenu";

import { useAuth } from "@/lib/auth-context";
import { useMobileDrawer } from "@/lib/mobile-drawer-context";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace-context";

interface RailNavItemProps {
  to: string;
  label: string;
  icon: ReactNode;
  match?: (pathname: string) => boolean;
  end?: boolean;
}

function RailNavItem({ to, label, icon, match, end }: RailNavItemProps) {
  const { pathname } = useLocation();
  const active = match ? match(pathname) : end ? pathname === to : pathname.startsWith(to);

  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={cn("rail-item", active && "active")}
      title={label}
    >
      {icon}
      <span className="rail-label">{label}</span>
    </Link>
  );
}

export function AppSidebar() {
  const { user, isOrgAdmin } = useAuth();
  const { isOpen } = useMobileDrawer();
  const { isTeamWorkspace } = useWorkspace();

  const showAdminNav = isTeamWorkspace && isOrgAdmin;
  const showMemberNav =
    isTeamWorkspace && Boolean(user?.org_id) && !isOrgAdmin;

  return (
    <aside
      id="app-sidebar"
      className={cn("app-sidebar rail relative h-full shrink-0", isOpen && "open")}
    >
      <Link to="/dashboard" className="rail-mark" aria-label="睿阁 · 概览">
        <RuigeLogo size={30} />
      </Link>
      <div className="rail-sep" />

      <nav className="rail-nav">
        <RailNavItem
          to="/dashboard"
          end
          label="概览"
          icon={<LayoutGrid className="h-[21px] w-[21px]" />}
        />
        <RailNavItem
          to="/knowledge-bases"
          match={isKbNavActive}
          label="资料库"
          icon={<Library className="h-[21px] w-[21px]" />}
        />
        <RailNavItem
          to="/ask"
          match={isChatNavActive}
          label="对话"
          icon={<MessageCircle className="h-[21px] w-[21px]" />}
        />

        {showAdminNav ? (
          <>
            <RailNavItem
              to="/organization/departments"
              label="组织与部门"
              icon={<Building2 className="h-[21px] w-[21px]" />}
            />
            <RailNavItem
              to="/organization/members"
              label="成员管理"
              icon={<Users className="h-[21px] w-[21px]" />}
            />
            <RailNavItem
              to="/organization/settings"
              label="团队设置"
              icon={<Settings className="h-[21px] w-[21px]" />}
            />
            <RailNavItem
              to="/admin/audit"
              label="操作审计"
              icon={<ClipboardList className="h-[21px] w-[21px]" />}
            />
          </>
        ) : null}

        {showMemberNav ? (
          <RailNavItem
            to="/organization/members"
            label="团队成员"
            icon={<Users className="h-[21px] w-[21px]" />}
          />
        ) : null}
      </nav>

      <div className="rail-spacer" />

      {/* 移动端抽屉内显示工作区 / 部门切换（桌面版在顶栏） */}
      <div className="rail-bottom-block md:hidden">
        <WorkspaceSwitcher />
        {isTeamWorkspace && <DepartmentPicker />}
      </div>

      <div className="rail-bottom-block">
        <RailNavItem
          to="/settings/account"
          label="账号设置"
          icon={<UserCircle className="h-[21px] w-[21px]" />}
        />
        <div className="mt-1 flex justify-center">
          <UserAvatarMenu size="sm" />
        </div>
      </div>
    </aside>
  );
}
