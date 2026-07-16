import { AuthField } from "@/components/auth/AuthField";
import { PasswordRequirements } from "@/components/auth/PasswordRequirements";
import type {
  RegisterTeamRole,
  RegisterUsage,
} from "@/components/auth/register-form-types";
import {
  formatRegisterSummaryChip,
  registerCredentialsSubtitle,
} from "@/components/auth/register-summary";
import { Button } from "@/components/ui/button";
import type { FieldErrors } from "@/lib/auth-form-validation";

interface RegisterCredentialsStepProps {
  usage: RegisterUsage;
  teamRole: RegisterTeamRole | null;
  orgName: string;
  inviteCode: string;
  resolvedOrgName?: string;
  username: string;
  email: string;
  nickname: string;
  showNickname: boolean;
  password: string;
  confirmPassword: string;
  fieldErrors: FieldErrors;
  loading: boolean;
  onUsernameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onNicknameChange: (value: string) => void;
  onShowNickname: () => void;
  onPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onBack: () => void;
  onSubmit: () => void;
}

export function RegisterCredentialsStep({
  usage,
  teamRole,
  orgName,
  inviteCode,
  resolvedOrgName,
  username,
  email,
  nickname,
  showNickname,
  password,
  confirmPassword,
  fieldErrors,
  loading,
  onUsernameChange,
  onEmailChange,
  onNicknameChange,
  onShowNickname,
  onPasswordChange,
  onConfirmPasswordChange,
  onBack,
  onSubmit,
}: RegisterCredentialsStepProps) {
  return (
    <>
      <span className="register-summary-chip">
        {formatRegisterSummaryChip({
          usage,
          teamRole,
          orgName,
          inviteCode,
          resolvedOrgName,
        })}
      </span>

      <div className="mb-3 mt-2 shrink-0">
        <h2 className="font-serif text-xl font-semibold tracking-[0.02em] text-[var(--auth-text)]">
          设置登录信息
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-[var(--auth-muted)]">
          {registerCredentialsSubtitle({ usage, teamRole })}
        </p>
      </div>

      <div className="register-step-scroll -mx-1 min-h-0 flex-1 overflow-y-auto px-1 pb-1">
        <div className="space-y-3.5">
          <AuthField
            id="username"
            label="用户名"
            autoComplete="username"
            value={username}
            maxLength={32}
            onChange={onUsernameChange}
            placeholder="3～32 位字母、数字或下划线"
            error={fieldErrors.username}
          />
          <AuthField
            id="email"
            label="邮箱"
            type="email"
            autoComplete="email"
            value={email}
            onChange={onEmailChange}
            placeholder="name@company.com"
            error={fieldErrors.email}
          />
          <AuthField
            id="password"
            label="密码"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={onPasswordChange}
            placeholder="至少 8 位，需包含大写、小写、数字与特殊字符"
            error={fieldErrors.password}
            showPasswordToggle
            showStrength
          />
          <PasswordRequirements password={password} />
          <AuthField
            id="confirmPassword"
            label="确认密码"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={onConfirmPasswordChange}
            placeholder="再次输入密码"
            error={fieldErrors.confirmPassword}
            showPasswordToggle
          />

          {!showNickname ? (
            <button
              type="button"
              className="text-xs text-[var(--auth-action)] underline-offset-2 hover:underline"
              onClick={onShowNickname}
            >
              + 添加昵称（可选，显示在侧栏）
            </button>
          ) : (
            <AuthField
              id="nickname"
              label={
                <>
                  昵称
                  <span className="ml-1 font-normal text-[var(--auth-muted)]">
                    （可选）
                  </span>
                </>
              }
              value={nickname}
              maxLength={64}
              onChange={onNicknameChange}
              placeholder="例如：小张"
            />
          )}
        </div>
      </div>

      <div className="mt-auto flex shrink-0 gap-2.5 pt-4">
        <Button type="button" variant="authOutline" className="min-w-[88px]" onClick={onBack}>
          上一步
        </Button>
        <Button
          type="button"
          variant="auth"
          className="flex-1"
          disabled={loading}
          onClick={onSubmit}
        >
          {loading ? "创建中…" : "创建账号"}
        </Button>
      </div>
    </>
  );
}
