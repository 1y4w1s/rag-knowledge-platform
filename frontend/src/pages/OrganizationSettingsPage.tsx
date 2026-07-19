import { useCallback, useEffect, useState } from "react";

import {
  SettingsFormCard,
  SettingsReadonlyField,
} from "@/components/settings/SettingsFormCard";
import { RequireTeamWorkspace } from "@/components/common/RequireTeamWorkspace";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { SectionTitle } from "@/components/common/SectionTitle";
import { Button } from "@/components/ui/button";
import {
  fetchOrganizationSettings,
  formatCreatedAt,
  updateOrganizationName,
  dissolveOrganization,
  type OrganizationSettings,
} from "@/lib/organization-api";
import { DissolveOrgDialog } from "@/components/organization/DissolveOrgDialog";
import { useWorkspace } from "@/lib/workspace-context";
import { setStoredWorkspace } from "@/lib/workspace-storage";
import { useNavigate } from "react-router-dom";
import { triggerOrgNameRefresh } from "@/lib/use-organization-name";
import { Toast, useToast } from "@/components/ui/Toast";

export function OrganizationSettingsPage() {
  const [settings, setSettings] = useState<OrganizationSettings | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [dissolveOpen, setDissolveOpen] = useState(false);
  const [dissolving, setDissolving] = useState(false);
  const [dissolveError, setDissolveError] = useState<string | null>(null);
  const { toast, show: showToast, dismiss: dismissToast } = useToast();

  const navigate = useNavigate();
  const { setWorkspace } = useWorkspace();

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOrganizationSettings();
      setSettings(data);
      setNameDraft(data.name);
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
    document.title = "睿阁 · 团队设置";
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", "管理团队名称与危险操作。");
    return () => {
      document.title = "睿阁";
    };
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === settings.name) return;

    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateOrganizationName(trimmed);
      setSettings(updated);
      setNameDraft(updated.name);
      showToast("团队名称已更新");
      triggerOrgNameRefresh();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const nameChanged = settings ? nameDraft.trim() !== settings.name : false;

  if (loading) {
    return (
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <div className="settings-page-quiet max-w-[560px] space-y-4">
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
            {error ?? "无法加载团队信息"}
          </AlertBanner>
        </div>
      </div>
    );
  }

  return (
    <RequireTeamWorkspace feature="团队设置">
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <SectionTitle label="团队设置" en="TEAM SETTINGS" tone="quiet" />
        <div className="settings-page-quiet max-w-[560px]">
          {saveError ? (
            <AlertBanner onDismiss={() => setSaveError(null)}>{saveError}</AlertBanner>
          ) : null}

          <SettingsFormCard title="团队信息">
            <form className="space-y-3.5" onSubmit={(e) => void handleSave(e)}>
              <div>
                <label htmlFor="org-name" className="settings-field-label">
                  团队名称
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="org-name"
                    type="text"
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    maxLength={255}
                    className="settings-field-input flex-1"
                    disabled={saving}
                  />
                  <Button
                    type="submit"
                    size="sm"
                    disabled={saving || !nameChanged || !nameDraft.trim()}
                  >
                    {saving ? "保存中…" : "保存"}
                  </Button>
                </div>
              </div>
              <SettingsReadonlyField
                id="org-created"
                label="创建时间"
                value={formatCreatedAt(settings.created_at)}
              />
              <SettingsReadonlyField
                id="org-member-count"
                label="成员数"
                value={String(settings.member_count)}
              />
            </form>
          </SettingsFormCard>

          <SettingsFormCard title="危险操作">
            <p className="mb-3 text-sm text-muted">
              解散将永久删除资料库、文档与成员记录。
            </p>
            {dissolveError ? (
              <AlertBanner onDismiss={() => setDissolveError(null)}>
                {dissolveError}
              </AlertBanner>
            ) : null}
            <button
              type="button"
              className="settings-danger-link"
              onClick={() => setDissolveOpen(true)}
            >
              解散团队
            </button>
          </SettingsFormCard>
        </div>

        <DissolveOrgDialog
          orgName={settings.name}
          open={dissolveOpen}
          onOpenChange={setDissolveOpen}
          dissolving={dissolving}
          onConfirm={async (confirmName: string) => {
            setDissolving(true);
            setDissolveError(null);
            try {
              await dissolveOrganization(confirmName);
              setDissolveOpen(false);
              setStoredWorkspace("personal");
              setWorkspace("personal");
              navigate("/dashboard", { replace: true });
            } catch (err) {
              setDissolveError(err instanceof Error ? err.message : "解散失败");
              setDissolveOpen(false);
            } finally {
              setDissolving(false);
            }
          }}
        />
      </div>

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </RequireTeamWorkspace>
  );
}
