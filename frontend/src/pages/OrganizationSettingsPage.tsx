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

export function OrganizationSettingsPage() {
  const [settings, setSettings] = useState<OrganizationSettings | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [dissolveOpen, setDissolveOpen] = useState(false);
  const [dissolving, setDissolving] = useState(false);
  const [dissolveError, setDissolveError] = useState<string | null>(null);

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
    meta.setAttribute(
      "content",
      "管理睿阁团队：编辑团队名称、查看创建时间与成员规模。",
    );
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
    setSaved(false);
    try {
      const updated = await updateOrganizationName(trimmed);
      setSettings(updated);
      setNameDraft(updated.name);
      setSaved(true);
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
          {error ?? "无法加载团队信息"}
        </AlertBanner>
      </div>
    );
  }

  return (
    <RequireTeamWorkspace feature="团队设置">
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
      <SectionTitle label="团队设置" en="TEAM SETTINGS" />
      <div className="max-w-[440px] space-y-4">
      {saveError ? (
        <AlertBanner onDismiss={() => setSaveError(null)}>{saveError}</AlertBanner>
      ) : null}
      {saved ? (
        <p className="rounded-[10px] border border-[var(--line2)] bg-[color:color-mix(in_srgb,var(--ubg)_65%,transparent)] px-4 py-2.5 text-sm text-muted">
          团队名称已更新
        </p>
      ) : null}

      <SettingsFormCard title="团队信息">
        <form className="space-y-3.5" onSubmit={(e) => void handleSave(e)}>
          <div>
            <label htmlFor="org-name" className="settings-field-label">
              团队名称
            </label>
            <input
              id="org-name"
              type="text"
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              maxLength={255}
              className="settings-field-input"
              disabled={saving}
            />
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
          <Button type="submit" size="sm" disabled={saving || !nameChanged || !nameDraft.trim()}>
            {saving ? "保存中…" : "保存"}
          </Button>
        </form>
      </SettingsFormCard>

      <div className="pt-4 border-t border-[var(--line2)]">
        <h3 className="font-serif text-base font-semibold text-[var(--bad)]">危险操作</h3>
        <p className="mt-1.5 text-sm text-muted">
          解散团队将永久删除所有资料库、文档和成员记录，不可恢复。
        </p>
        {dissolveError ? (
          <AlertBanner onDismiss={() => setDissolveError(null)}>{dissolveError}</AlertBanner>
        ) : null}
        <Button
          type="button"
          size="sm"
          className="mt-3 bg-[var(--bad)] text-white hover:bg-[var(--bad)]/80"
          onClick={() => setDissolveOpen(true)}
        >
          解散团队
        </Button>
      </div>

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
    </RequireTeamWorkspace>
  );
}
