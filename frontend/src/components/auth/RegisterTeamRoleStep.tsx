import { RegisterChoiceCard } from "@/components/auth/RegisterChoiceCard";
import type { RegisterTeamRole } from "@/components/auth/register-form-types";
import { teamRoleStepSubtitle } from "@/components/auth/register-summary";
import { AuthField } from "@/components/auth/AuthField";
import { Button } from "@/components/ui/button";
import { orgNameTrimLen } from "@/lib/auth-form-validation";
import type { FieldErrors } from "@/lib/auth-form-validation";

interface RegisterTeamRoleStepProps {
  teamRole: RegisterTeamRole | null;
  orgName: string;
  inviteCode: string;
  fieldErrors: FieldErrors;
  onSelectRole: (role: RegisterTeamRole) => void;
  onOrgNameChange: (value: string) => void;
  onInviteCodeChange: (value: string) => void;
  onBack: () => void;
  onContinue: () => void;
  canContinue: boolean;
  continueLoading?: boolean;
}

export function RegisterTeamRoleStep({
  teamRole,
  orgName,
  inviteCode,
  fieldErrors,
  onSelectRole,
  onOrgNameChange,
  onInviteCodeChange,
  onBack,
  onContinue,
  canContinue,
  continueLoading = false,
}: RegisterTeamRoleStepProps) {
  const trimLen = orgNameTrimLen(orgName);

  return (
    <>
      <div className="mb-3 shrink-0">
        <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
          团队里你的角色
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-[var(--auth-muted)]">
          {teamRoleStepSubtitle(teamRole)}
        </p>
      </div>

      <div className="register-step-scroll -mx-1 min-h-0 flex-1 overflow-y-auto px-1">
        <div className="space-y-2.5" role="radiogroup" aria-label="团队角色">
          <RegisterChoiceCard
            selected={teamRole === "creator"}
            title="创建者"
            hint="创建新团队并成为管理员"
            onSelect={() => onSelectRole("creator")}
          />
          <RegisterChoiceCard
            selected={teamRole === "member"}
            title="成员"
            hint="凭邀请码加入已有团队"
            onSelect={() => onSelectRole("member")}
          />
        </div>

        {!teamRole && (
          <p className="mt-3 text-center text-xs text-[var(--auth-muted)]">
            请选择上方角色以继续
          </p>
        )}

        {fieldErrors.teamRole && (
          <p className="mt-2 text-xs text-[var(--auth-strength-weak)]" role="alert">
            {fieldErrors.teamRole}
          </p>
        )}

        {teamRole === "creator" && (
          <div className="mt-4 space-y-2">
            <AuthField
              id="orgDisplayName"
              label="团队显示名称 *"
              value={orgName}
              maxLength={255}
              onChange={onOrgNameChange}
              placeholder="例如：睿阁科技"
              error={fieldErrors.orgName}
              hint="用于侧栏展示，建议 20 字以内；更长名称可在组织设置修改"
            />
            <div className="flex justify-end px-0.5">
              <span
                className={[
                  "text-[0.65rem] tabular-nums text-[var(--auth-muted)]",
                  trimLen > 80 ? "font-bold text-[#b45309]" : "",
                  trimLen > 40 && trimLen <= 80 ? "font-semibold text-[#92400e]" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {trimLen} / 255
              </span>
            </div>
            {trimLen > 80 && (
              <p className="register-soft-confirm" role="status">
                <strong>名称较长</strong>
                · 侧栏可能显示不全，继续前会请你确认。
              </p>
            )}
            {trimLen > 40 && trimLen <= 80 && (
              <p className="register-soft-warn" role="status">
                已 {trimLen} 字，偏长；建议缩短或在组织设置中改用简称。
              </p>
            )}
          </div>
        )}

        {teamRole === "member" && (
          <div className="mt-4 space-y-2">
            <AuthField
              id="inviteCode"
              label="邀请码 *"
              value={inviteCode}
              onChange={onInviteCodeChange}
              placeholder="例如：ZHIAN-8K2F"
              error={fieldErrors.inviteCode}
              hint="向团队管理员索取；无效或过期将无法注册"
            />
            <div className="register-info-box" role="note">
              没有邀请码？返回上一步选 <strong>个人</strong>
              ，登录后在账号设置填码，或由管理员添加你的邮箱。
            </div>
          </div>
        )}
      </div>

      <div className="mt-auto flex shrink-0 gap-2.5 pt-4">
        <Button type="button" variant="authOutline" className="min-w-[88px]" onClick={onBack}>
          上一步
        </Button>
        <Button
          type="button"
          variant="auth"
          className="flex-1"
          disabled={!canContinue || continueLoading}
          onClick={onContinue}
        >
          {continueLoading ? "校验中…" : "继续"}
        </Button>
      </div>
    </>
  );
}
