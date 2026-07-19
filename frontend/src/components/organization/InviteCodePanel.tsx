import { useState } from "react";

import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import {
  createOrganizationInvite,
  formatInviteExpiry,
  type OrganizationInvite,
} from "@/lib/organization-api";

interface InviteCodePanelProps {
  onAddByEmail?: () => void;
}

export function InviteCodePanel({ onAddByEmail }: InviteCodePanelProps) {
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
    <section className="org-invite-bar">
      <h3 className="org-invite-bar-title">邀请码</h3>
      <p className="org-invite-bar-hint">注册时填写即可加入</p>

      {error ? (
        <div className="w-full basis-full">
          <AlertBanner onDismiss={() => setError(null)}>{error}</AlertBanner>
        </div>
      ) : null}

      {invite ? (
        <>
          <code className="org-invite-code">{invite.code}</code>
          <Button type="button" variant="outline" size="sm" onClick={() => void handleCopy()}>
            {copied ? "已复制" : "复制"}
          </Button>
          <span className="text-[0.72rem] text-muted">
            {formatInviteExpiry(invite.expires_at)}
          </span>
        </>
      ) : null}

      <Button
        type="button"
        size="sm"
        variant={invite ? "outline" : "default"}
        disabled={generating}
        onClick={() => void handleGenerate()}
      >
        {generating ? "生成中…" : invite ? "重新生成" : "生成邀请码"}
      </Button>

      {onAddByEmail ? (
        <button type="button" className="org-invite-email-link" onClick={onAddByEmail}>
          邮箱添加…
        </button>
      ) : null}
    </section>
  );
}
