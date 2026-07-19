import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ChangePasswordForm } from "@/components/settings/ChangePasswordForm";
import { JoinTeamForm } from "@/components/settings/JoinTeamForm";
import { LeaveTeamForm } from "@/components/settings/LeaveTeamForm";
import { ApiKeyManager } from "@/components/settings/ApiKeyManager";
import {
  SettingsFormCard,
  SettingsReadonlyField,
} from "@/components/settings/SettingsFormCard";
import { SectionTitle } from "@/components/common/SectionTitle";
import { RequireTeamWorkspace } from "@/components/common/RequireTeamWorkspace";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Toast, useToast } from "@/components/ui/Toast";
import { fetchCurrentUser } from "@/lib/auth-api";
import { useAuth } from "@/lib/auth-context";
import { getAccessToken, saveAuthSession } from "@/lib/auth-storage";
import {
  changeAccountPassword,
  fetchAccountSettings,
  formatAccountTypeLabel,
  updateAccountProfile,
  type AccountSettings,
} from "@/lib/settings-api";
import { useWorkspace } from "@/lib/workspace-context";
import { setStoredWorkspace } from "@/lib/workspace-storage";

export function AccountSettingsPage() {
  const navigate = useNavigate();
  const { logout, syncFromStorage, user } = useAuth();
  const { setWorkspace, redirectWithGuardToast } = useWorkspace();
  const { toast, show: showToast, dismiss: dismissToast } = useToast();
  const [settings, setSettings] = useState<AccountSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nicknameDraft, setNicknameDraft] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

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
    setNicknameDraft(settings?.nickname ?? "");
  }, [settings?.nickname]);

  async function handleSaveNickname() {
    if (!settings) return;
    setSavingProfile(true);
    setProfileError(null);
    try {
      const trimmed = nicknameDraft.trim();
      const next = await updateAccountProfile({ nickname: trimmed || null });
      setSettings(next);
      showToast("昵称已更新");
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSavingProfile(false);
    }
  }

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    document.title = "睿阁 · 账号设置";
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", "管理睿阁账号信息与安全设置。");
    return () => {
      document.title = "睿阁";
    };
  }, []);

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
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <div className="settings-page-quiet max-w-[600px] space-y-4">
          <div className="settings-card animate-pulse space-y-4">
            <div className="h-5 w-24 rounded bg-border/80" />
            <div className="h-10 rounded bg-border/60" />
            <div className="h-10 rounded bg-border/60" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !settings) {
    return (
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
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
      </div>
    );
  }

  return (
    <>
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <SectionTitle label="账号设置" en="ACCOUNT" tone="quiet" />
        <div className="settings-page-quiet max-w-[600px] space-y-0">
          <div id="account-profile">
            <SettingsFormCard title="账号信息">
              <div className="space-y-3.5">
                <SettingsReadonlyField
                  id="account-email"
                  label="邮箱"
                  value={settings.email}
                />
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
                <div>
                  <label htmlFor="account-nickname" className="settings-field-label">
                    昵称
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      id="account-nickname"
                      type="text"
                      value={nicknameDraft}
                      onChange={(e) => {
                        setNicknameDraft(e.target.value);
                        if (profileError) setProfileError(null);
                      }}
                      maxLength={64}
                      placeholder="选填"
                      className="settings-field-input flex-1"
                      disabled={savingProfile}
                    />
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void handleSaveNickname()}
                      disabled={
                        savingProfile ||
                        nicknameDraft === (settings.nickname ?? "")
                      }
                    >
                      {savingProfile ? "保存中…" : "保存"}
                    </Button>
                  </div>
                  {profileError ? (
                    <p role="alert" className="mt-1 text-xs text-[var(--bad)]">
                      {profileError}
                    </p>
                  ) : null}
                </div>
              </div>
            </SettingsFormCard>
          </div>

          <div id="account-security">
            <ChangePasswordForm onSubmit={handlePasswordChange} />
          </div>

          {!settings.org_id ? (
            <JoinTeamForm
              onJoined={(message, orgId) => void handleJoined(message, orgId)}
            />
          ) : (
            <RequireTeamWorkspace feature="离开团队">
              <LeaveTeamForm
                orgName={settings.org_name ?? "团队"}
                isOwner={Boolean(user?.is_owner)}
                onLeft={(message) => void handleLeft(message)}
              />
            </RequireTeamWorkspace>
          )}

          <ApiKeyManager />

          <SettingsFormCard title="会话">
            <button
              type="button"
              className="settings-logout-btn"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              退出登录
            </button>
          </SettingsFormCard>
        </div>
      </div>

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </>
  );
}
