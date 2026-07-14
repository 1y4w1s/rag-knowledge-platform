import { useState } from "react";

import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { INVITE_INVALID_MSG } from "@/lib/auth-invite-api";
import { joinTeamWithInviteCode } from "@/lib/settings-api";
import { cn } from "@/lib/utils";

interface JoinTeamFormProps {
  onJoined: (message: string, orgId: string) => void;
}

export function JoinTeamForm({ onJoined }: JoinTeamFormProps) {
  const [inviteCode, setInviteCode] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const trimmed = inviteCode.trim();
    if (trimmed.length < 4) {
      setFieldError("请填写有效邀请码");
      return;
    }
    setFieldError(null);

    setSubmitting(true);
    try {
      const result = await joinTeamWithInviteCode(trimmed);
      onJoined(result.message, result.account.org_id!);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "加入失败，请稍后重试";
      if (message.includes("邀请码")) {
        setFieldError("邀请码无效或已过期");
        setFormError(INVITE_INVALID_MSG);
      } else {
        setFormError(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SettingsFormCard title="加入团队" className="settings-card mt-4">
      <p className="mb-4 text-sm leading-relaxed text-muted">
        已有个人账号？填写管理员提供的邀请码即可加入团队空间；加入后可在侧栏切换「我的空间」与团队。
      </p>

      <form className="space-y-4" onSubmit={(e) => void handleSubmit(e)} noValidate>
        {formError ? (
          <div
            role="alert"
            className="rounded-md border border-[color:var(--status-err-border)] bg-[color:var(--status-err-bg)] px-3 py-2 text-sm text-[color:var(--status-err-text)]"
          >
            {formError}
          </div>
        ) : null}

        <div>
          <Label htmlFor="join-invite-code" className="settings-field-label">
            邀请码
          </Label>
          <Input
            id="join-invite-code"
            value={inviteCode}
            onChange={(e) => {
              setInviteCode(e.target.value);
              if (fieldError) setFieldError(null);
              if (formError) setFormError(null);
            }}
            placeholder="例如：ZHIAN-8K2F"
            autoComplete="off"
            aria-invalid={Boolean(fieldError)}
            aria-describedby={fieldError ? "join-invite-code-error" : undefined}
            className={cn(
              "settings-field-input",
              fieldError &&
                "border-[color:var(--status-err-border)] focus-visible:ring-[color:rgb(232_180_160/0.35)]",
            )}
          />
          {fieldError ? (
            <p
              id="join-invite-code-error"
              className="mt-1.5 text-xs text-[color:var(--status-err-text)]"
              role="alert"
            >
              {fieldError}
            </p>
          ) : (
            <p className="mt-1.5 text-[0.78rem] text-muted">
              向团队管理员索取；无效或过期将无法加入
            </p>
          )}
        </div>

        <Button
          type="submit"
          variant="brand"
          className="mt-1 w-full sm:w-auto"
          disabled={submitting}
        >
          {submitting ? "加入中…" : "加入团队"}
        </Button>
      </form>
    </SettingsFormCard>
  );
}
