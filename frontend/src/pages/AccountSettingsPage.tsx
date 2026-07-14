import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ChangePasswordForm } from "@/components/settings/ChangePasswordForm";
import { JoinTeamForm } from "@/components/settings/JoinTeamForm";
import { LeaveTeamForm } from "@/components/settings/LeaveTeamForm";
import {
  SettingsFormCard,
  SettingsReadonlyField,
} from "@/components/settings/SettingsFormCard";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { EmptyStateV44, ACCOUNT_SCENE } from "@/components/ui/EmptyState";
import { fetchCurrentUser } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { getAccessToken, saveAuthSession } from "@/lib/auth-storage";
import {
  changeAccountPassword,
  fetchAccountSettings,
  formatAccountTypeLabel,
  type AccountSettings,
} from "@/lib/settings-api";
import { useWorkspace } from "@/lib/workspace-context";
import { setStoredWorkspace } from "@/lib/workspace-storage";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const { logout, syncFromStorage, user } = useAuth();
  const { setWorkspace, redirectWithGuardToast } = useWorkspace();
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSettings(await fetchAccountSettings());
    } catch (err) {
      setSettings(null);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    document.title = "知岸 · 账号设置";
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    meta.setAttribute(
      "content",
      "管理知岸账号：查看账号信息、修改登录密码、加入或离开团队空间。",
    );
    return () => {
      document.title = "知岸";
    };
  }, []);

  function scrollToId(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handlePasswordChange(
    currentPassword: string,
    newPassword: string,
  ) {
    await changeAccountPassword(currentPassword, newPassword);
    logout();
    navigate("/login?notice=password-changed", { replace: true });
  }

  async function handleLeft(message: string) {
    const freshUser = await fetchCurrentUser();
    const token = getAccessToken();
    if (token) saveAuthSession(token, freshUser);
    syncFromStorage();
    setStoredWorkspace("personal");
    setWorkspace("personal");
    setSettings(await fetchAccountSettings());
    redirectWithGuardToast(message, "/dashboard");
  }

  async function handleJoined(message: string, orgId: string) {
    const freshUser = await fetchCurrentUser();
    const token = getAccessToken();
    if (token) saveAuthSession(token, freshUser);
    syncFromStorage();
    setStoredWorkspace(orgId);
    setWorkspace(orgId);
    setSettings(await fetchAccountSettings());
    redirectWithGuardToast(message, "/dashboard");
  }

  if (loading) {
    return (
      <div className="max-w-[440px] space-y-4">
        <div className="settings-card animate-pulse space-y-4">
          <div className="h-5 w-24 rounded bg-border/80" />
          <div className="h-10 rounded bg-border/60" />
          <div className="h-10 rounded bg-border/60" />
          <div className="h-10 rounded bg-border/60" />
        </div>
      </div>
    );
  }

  if (error || !settings) {
    return (
      <div className="max-w-[440px]">
        <AlertBanner
          action={
            <Button type="button" variant="outline" size="sm" onClick={loadSettings}>
              重试
            </Button>
          }
        >
          {error ?? "无法加载账号信息"}
        </AlertBanner>
      </div>
    );
  }

  return (
    <div className="max-w-[440px]">
      <h2 className="mb-4 font-serif text-xl font-semibold tracking-[0.02em] text-foreground">
        账号设置
      </h2>
      <div id="account-profile">
        <SettingsFormCard title="账号信息">
          <div className="space-y-3.5">
            <SettingsReadonlyField id="account-email" label="邮箱" value={settings.email} />
            <SettingsReadonlyField
              id="account-type"
              label="账号类型"
              value={formatAccountTypeLabel(settings)}
            />
            {settings.org_name ? (
              <SettingsReadonlyField
                id="account-org"
                label="所属团队"
                value={settings.org_name}
              />
            ) : null}
          </div>
        </SettingsFormCard>
      </div>

      {!settings.org_id ? (
        <>
          <EmptyStateV44
            scene={{
              ...ACCOUNT_SCENE,
              ctaPrimary: {
                ...ACCOUNT_SCENE.ctaPrimary,
                onClick: () => scrollToId("account-profile"),
              },
              ctaSecondary: {
                ...ACCOUNT_SCENE.ctaSecondary,
                onClick: () => scrollToId("account-security"),
              },
            }}
          />
          <JoinTeamForm onJoined={(message, orgId) => void handleJoined(message, orgId)} />
        </>
      ) : (
        <LeaveTeamForm
          orgName={settings.org_name ?? "团队"}
          isOwner={Boolean(user?.is_owner)}
          onLeft={(message) => void handleLeft(message)}
        />
      )}

      <div id="account-security">
        <ChangePasswordForm onSubmit={handlePasswordChange} />
      </div>
    </div>
  );
}
