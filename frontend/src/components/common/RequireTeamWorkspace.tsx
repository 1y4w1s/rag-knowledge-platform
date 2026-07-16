import type { ReactNode } from "react";
import { Building2 } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { useWorkspace } from "@/lib/workspace-context";
import { Button } from "@/components/ui/button";

interface RequireTeamWorkspaceProps {
  children: ReactNode;
  /** 列表/设置/部门 — 用于空态文案 */
  feature?: string;
}

/**
 * 团队专属页守卫：仅在 team workspace 下渲染 children。
 * personal 视角下显示空态卡 + "切到团队" CTA，避免误触发 fetch 与视觉错位。
 */
export function RequireTeamWorkspace({
  children,
  feature = "该功能",
}: RequireTeamWorkspaceProps) {
  const { isTeamWorkspace, setWorkspace } = useWorkspace();
  const { user } = useAuth();
  const orgId = user?.org_id ?? null;

  if (isTeamWorkspace) {
    return <>{children}</>;
  }

  return (
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
      <section aria-label="需要切换到团队工作区">
        <div className="mx-auto mt-6 max-w-xl rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-8 text-center shadow-[var(--card-shadow)]">
          <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-[var(--action-bg)] text-[var(--action)]">
            <Building2 className="h-6 w-6" aria-hidden="true" />
          </div>
          <h2 className="font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            请先切换到团队工作区
          </h2>
          <p className="mt-2 text-sm leading-[1.65] text-[var(--mut-warm)]">
            {feature}需要在团队工作区下使用。点击下方按钮切到团队视角后即可继续。
          </p>
          {orgId ? (
            <Button
              type="button"
              size="default"
              variant="brand"
              className="mt-5"
              onClick={() => setWorkspace(orgId)}
            >
              切到团队
            </Button>
          ) : (
            <p className="mt-5 text-sm text-[var(--mut)]">
              当前账号尚未加入任何团队，请联系管理员邀请。
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
