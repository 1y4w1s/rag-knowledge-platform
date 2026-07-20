import { lazy, Suspense, type ReactNode } from "react";
import {
  createBrowserRouter,
  Navigate,
  type RouteObject,
} from "react-router-dom";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import {
  AppShellLayout,
  type ShellRouteHandle,
} from "@/components/layout/AppShellLayout";
import { OrgAdminGuard } from "@/components/layout/OrgAdminGuard";
import { ResourceGuard } from "@/components/guards/ResourceGuard";
import { RequireTeamWorkspace } from "@/components/common/RequireTeamWorkspace";

// 路由级懒加载：每个页面拆为独立 chunk，首屏只下载当前路由所需代码。
// 页面均为命名导出，故用 .then(m => ({ default: m.X })) 适配 React.lazy。
const LoginPage = lazy(() =>
  import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const ForgotPasswordPage = lazy(() =>
  import("@/pages/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })),
);
const ResetPasswordPage = lazy(() =>
  import("@/pages/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })),
);
const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const AskPage = lazy(() =>
  import("@/pages/AskPage").then((m) => ({ default: m.AskPage })),
);
const ChatPage = lazy(() =>
  import("@/pages/ChatPage").then((m) => ({ default: m.ChatPage })),
);
const KnowledgeBasesPage = lazy(() =>
  import("@/pages/KnowledgeBasesPage").then((m) => ({
    default: m.KnowledgeBasesPage,
  })),
);
const KnowledgeBaseDetailPage = lazy(() =>
  import("@/pages/KnowledgeBaseDetailPage").then((m) => ({
    default: m.KnowledgeBaseDetailPage,
  })),
);
const DocumentPreviewPage = lazy(() =>
  import("@/pages/DocumentPreviewPage").then((m) => ({
    default: m.DocumentPreviewPage,
  })),
);
const AccountSettingsPage = lazy(() =>
  import("@/pages/AccountSettingsPage").then((m) => ({
    default: m.AccountSettingsPage,
  })),
);
const MembersPage = lazy(() =>
  import("@/pages/MembersPage").then((m) => ({ default: m.MembersPage })),
);
const OrgDepartmentsPage = lazy(() =>
  import("@/pages/OrgDepartmentsPage").then((m) => ({
    default: m.OrgDepartmentsPage,
  })),
);
const OrganizationSettingsPage = lazy(() =>
  import("@/pages/OrganizationSettingsPage").then((m) => ({
    default: m.OrganizationSettingsPage,
  })),
);
const EvaluationsPage = lazy(() =>
  import("@/pages/EvaluationsPage").then((m) => ({
    default: m.EvaluationsPage,
  })),
);
const AdminAuditPage = lazy(() =>
  import("@/pages/AdminAuditPage").then((m) => ({ default: m.AdminAuditPage })),
);
const AboutPage = lazy(() =>
  import("@/pages/AboutPage").then((m) => ({ default: m.AboutPage })),
);

function RouteFallback() {
  return (
    <div
      className="flex min-h-[40vh] w-full items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <span
        className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--line2)] border-t-[var(--action)]"
        aria-hidden="true"
      />
      <span className="sr-only">加载中…</span>
    </div>
  );
}

function shellPage(
  path: string,
  element: ReactNode,
  handle: ShellRouteHandle,
): RouteObject {
  return {
    path,
    element: <Suspense fallback={<RouteFallback />}>{element}</Suspense>,
    handle,
  };
}

const appRoutes: RouteObject[] = [
  shellPage("dashboard", <DashboardPage />, { breadcrumb: <>概览</> }),
  shellPage("evaluations", <EvaluationsPage />, { breadcrumb: <>评测</> }),
  shellPage(
    "ask",
    <AskPage />,
    {
      breadcrumb: <>对话</>,
      trailing: (
        <span className="rounded-full bg-[#EFEBE6] px-2.5 py-0.5 text-[0.68rem] font-medium text-[#524A44]">
          引用溯源
        </span>
      ),
    },
  ),
  shellPage("knowledge-bases", <KnowledgeBasesPage />, { breadcrumb: <>资料库</> }),
  shellPage(
    "knowledge-bases/:id",
    <ResourceGuard>
      <KnowledgeBaseDetailPage />
    </ResourceGuard>,
    {
      breadcrumb: (
        <>
          资料库 / <b>详情</b>
        </>
      ),
    },
  ),
  shellPage(
    "knowledge-bases/:id/documents/:docId",
    <ResourceGuard>
      <DocumentPreviewPage />
    </ResourceGuard>,
    {
      breadcrumb: (
        <>
          资料库 / 文档 / <b>预览</b>
        </>
      ),
    },
  ),
  shellPage(
    "knowledge-bases/:id/chat",
    <ResourceGuard>
      <ChatPage />
    </ResourceGuard>,
    {
      breadcrumb: (
        <>
          对话 / <b>演示资料库</b>
        </>
      ),
      trailing: (
        <span className="rounded-full bg-[#EFEBE6] px-2.5 py-0.5 text-[0.68rem] font-medium text-[#524A44]">
          引用溯源
        </span>
      ),
    },
  ),
  shellPage("settings/account", <AccountSettingsPage />, {
    breadcrumb: <>账号设置</>,
  }),
  shellPage("about", <AboutPage />, {
    breadcrumb: <>关于睿阁</>,
  }),
  shellPage(
    "organization/members",
    <RequireTeamWorkspace feature="成员管理">
      <MembersPage />
    </RequireTeamWorkspace>,
    {
      breadcrumb: <>成员管理</>,
    },
  ),
  shellPage(
    "organization/departments",
    <RequireTeamWorkspace feature="组织与部门管理">
      <OrgAdminGuard>
        <OrgDepartmentsPage />
      </OrgAdminGuard>
    </RequireTeamWorkspace>,
    {
      breadcrumb: <>组织与部门</>,
    },
  ),
  shellPage(
    "organization/settings",
    <RequireTeamWorkspace feature="团队设置">
      <OrgAdminGuard>
        <OrganizationSettingsPage />
      </OrgAdminGuard>
    </RequireTeamWorkspace>,
    {
      breadcrumb: <>团队设置</>,
    },
  ),
  shellPage(
    "admin/audit",
    <RequireTeamWorkspace feature="操作审计">
      <OrgAdminGuard>
        <AdminAuditPage />
      </OrgAdminGuard>
    </RequireTeamWorkspace>,
    {
      breadcrumb: <>操作审计</>,
    },
  ),
];

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <Suspense fallback={<RouteFallback />}>
        <LoginPage />
      </Suspense>
    ),
  },
  {
    path: "/forgot-password",
    element: (
      <Suspense fallback={<RouteFallback />}>
        <ForgotPasswordPage />
      </Suspense>
    ),
  },
  {
    path: "/reset-password",
    element: (
      <Suspense fallback={<RouteFallback />}>
        <ResetPasswordPage />
      </Suspense>
    ),
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShellLayout />,
        children: appRoutes,
      },
    ],
  },
  { path: "/", element: <Navigate to="/dashboard" replace /> },
  { path: "*", element: <Navigate to="/dashboard" replace /> },
]);
