import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";

import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { Button } from "@/components/ui/button";
import { leaveTeam } from "@/lib/settings-api";

interface LeaveTeamFormProps {
  orgName: string;
  isOwner: boolean;
  onLeft: (message: string) => void;
}

export function LeaveTeamForm({ orgName, isOwner, onLeft }: LeaveTeamFormProps) {
  const titleId = useId();
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!confirmOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) setConfirmOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [confirmOpen, submitting]);

  async function handleConfirmLeave() {
    setFormError(null);
    setSubmitting(true);
    try {
      const result = await leaveTeam();
      setConfirmOpen(false);
      onLeft(result.message);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "离开失败，请稍后重试");
      setConfirmOpen(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <SettingsFormCard title="离开团队">
        {isOwner ? (
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-muted">
              所有者无法直接离开。请先在
              <Link
                to="/organization/members"
                className="mx-1 font-medium text-accent underline-offset-2 hover:underline"
              >
                成员管理
              </Link>
              转让所有权。
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm leading-relaxed text-muted">
              离开「{orgName}」后回到个人空间。
            </p>

            {formError ? (
              <div
                role="alert"
                className="rounded-md border border-[color:var(--status-err-border)] bg-[color:var(--status-err-bg)] px-3 py-2 text-sm text-[color:var(--status-err-text)]"
              >
                {formError}
              </div>
            ) : null}

            <Button
              type="button"
              variant="outline"
              className="border-[color:var(--status-err-border)] text-[color:var(--status-err-text)] hover:bg-[color:var(--status-err-bg)]"
              disabled={submitting}
              onClick={() => setConfirmOpen(true)}
            >
              离开团队
            </Button>
          </div>
        )}
      </SettingsFormCard>

      {confirmOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="presentation"
          onClick={() => {
            if (!submitting) setConfirmOpen(false);
          }}
        >
          <div className="absolute inset-0 bg-black/30" aria-hidden />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="relative z-10 w-full max-w-md rounded-xl border border-[var(--line2)] bg-white p-6 shadow-md"
            onClick={(e) => e.stopPropagation()}
          >
            <h2
              id={titleId}
              className="font-serif text-lg font-semibold tracking-[0.02em] text-foreground"
            >
              确认离开团队
            </h2>
            <p className="mt-2 text-sm text-muted">
              确定离开「{orgName}」？离开后侧栏将只显示「我的空间」，团队资料库不再可访问。
            </p>

            <div className="mt-6 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={submitting}
                onClick={() => setConfirmOpen(false)}
              >
                取消
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={submitting}
                onClick={() => void handleConfirmLeave()}
                className="bg-[color:var(--status-err)] text-white hover:bg-[color:var(--status-err-text)]"
              >
                {submitting ? "离开中…" : "确认离开"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
