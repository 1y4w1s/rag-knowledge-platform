import { useState } from "react";

import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import {
  createOrganizationInvite,
  formatInviteExpiry,
  type OrganizationInvite,
} from "@/lib/organization-api";

export function InviteCodePanel() {
  const [invite, setInvite] = useState<OrganizationInvite | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    setCopied(false);
    try {
      const created = await createOrganizationInvite();
      setInvite(created);
    } catch (err) {
      setInvite(null);
      setError(err instanceof Error ? err.message : "生成失败");
    } finally {
      setGenerating(false);
    }
  }

  async function handleCopy() {
    if (!invite) return;
    try {
      await navigator.clipboard.writeText(invite.code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setError("复制失败，请手动选择邀请码");
    }
  }

  return (
    <SettingsFormCard title="邀请新成员" className="settings-card max-w-none">
      <p className="mb-4 text-sm leading-relaxed text-muted">
        生成邀请码后，新同事在注册页选择「团队 · 成员」并填写此码即可加入。同一邀请码可供多人使用。
      </p>

      {error ? (
        <div className="mb-4">
          <AlertBanner onDismiss={() => setError(null)}>{error}</AlertBanner>
        </div>
      ) : null}

      {invite ? (
        <div className="space-y-3">
          <div>
            <p className="settings-field-label">当前邀请码</p>
            <div className="flex flex-wrap items-center gap-2 rounded-[10px] border border-[var(--line2)] bg-[rgba(245,242,237,0.65)] px-3 py-2.5">
              <code className="min-w-0 flex-1 break-all font-mono text-[1.05rem] font-semibold tracking-[0.08em] text-foreground">
                {invite.code}
              </code>
              <Button type="button" variant="outline" size="sm" onClick={() => void handleCopy()}>
                {copied ? "已复制" : "复制"}
              </Button>
            </div>
          </div>
          <p className="text-[0.78rem] text-muted">{formatInviteExpiry(invite.expires_at)}</p>
        </div>
      ) : null}

      <div className={invite ? "mt-4" : undefined}>
        <Button type="button" size="sm" disabled={generating} onClick={() => void handleGenerate()}>
          {generating ? "生成中…" : invite ? "重新生成" : "生成邀请码"}
        </Button>
      </div>
    </SettingsFormCard>
  );
}
