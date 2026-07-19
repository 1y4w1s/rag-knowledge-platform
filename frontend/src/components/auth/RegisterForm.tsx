import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AuthFormAlert } from "@/components/auth/AuthField";
import { RegisterCredentialsStep } from "@/components/auth/RegisterCredentialsStep";
import { RegisterStepsIndicator } from "@/components/auth/RegisterStepsIndicator";
import { RegisterTeamRoleStep } from "@/components/auth/RegisterTeamRoleStep";
import type {
  RegisterTeamRole,
  RegisterUsage,
  RegisterWizardStep,
} from "@/components/auth/register-form-types";
import { RegisterUsageStep } from "@/components/auth/RegisterUsageStep";
import { registerAndLogin, validateUsernameClient } from "@/lib/auth-api";
import {
  INVITE_INVALID_MSG,
  validateInviteCode,
} from "@/lib/auth-invite-api";
import { useAuth } from "@/lib/auth-context";
import {
  confirmLongOrgName,
  needsLongOrgNameConfirm,
  orgNameTrimLen,
  validateRegisterCredentials,
  validateRegisterTeamRole,
  type FieldErrors,
} from "@/lib/auth-form-validation";
import { setStoredWorkspace } from "@/lib/workspace-storage";

interface RegisterFormProps {
  redirectTo: string;
  onSwitchToLogin: () => void;
}

function canContinueTeamStep(
  teamRole: RegisterTeamRole | null,
  orgName: string,
  inviteCode: string,
): boolean {
  if (!teamRole) return false;
  if (teamRole === "creator") {
    const len = orgNameTrimLen(orgName);
    return len >= 1 && len <= 255;
  }
  return inviteCode.trim().length >= 4;
}

/** WS-1-2 · 注册三步向导（W5+-1 UI · W5+-2 邀请码） */
export function RegisterForm({
  redirectTo,
  onSwitchToLogin,
}: RegisterFormProps) {
  const navigate = useNavigate();
  const { applySession } = useAuth();
  const confirmLockRef = useRef(false);

  const [step, setStep] = useState<RegisterWizardStep>(1);
  const [usage, setUsage] = useState<RegisterUsage | null>(null);
  const [teamRole, setTeamRole] = useState<RegisterTeamRole | null>(null);
  const [orgName, setOrgName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [resolvedOrgName, setResolvedOrgName] = useState("");

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");
  const [showNickname, setShowNickname] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [suggestLogin, setSuggestLogin] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validatingInvite, setValidatingInvite] = useState(false);

  function clearFieldError(key: string) {
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function handleSelectUsage(next: RegisterUsage) {
    setUsage(next);
    setTeamRole(null);
    setOrgName("");
    setInviteCode("");
    setResolvedOrgName("");
    setFieldErrors({});
  }

  function handleSelectRole(role: RegisterTeamRole) {
    setTeamRole(role);
    setResolvedOrgName("");
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next.teamRole;
      delete next.orgName;
      delete next.inviteCode;
      return next;
    });
  }

  function goUsageContinue() {
    if (!usage) return;
    setStep(usage === "personal" ? 3 : 2);
  }

  async function goTeamContinue() {
    const errors = validateRegisterTeamRole({
      teamRole,
      orgName,
      inviteCode,
    });
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (
      teamRole === "creator" &&
      needsLongOrgNameConfirm(orgName) &&
      !runLongNameConfirm("继续")
    ) {
      return;
    }

    if (teamRole === "member") {
      setApiError(null);
      setValidatingInvite(true);
      try {
        const result = await validateInviteCode(inviteCode);
        setResolvedOrgName(result.org_name);
        setStep(3);
      } catch {
        setApiError(INVITE_INVALID_MSG);
        setFieldErrors((prev) => ({
          ...prev,
          inviteCode: "邀请码无效或已过期",
        }));
      } finally {
        setValidatingInvite(false);
      }
      return;
    }

    setStep(3);
  }

  function runLongNameConfirm(actionLabel: string): boolean {
    if (confirmLockRef.current) return false;
    confirmLockRef.current = true;
    try {
      return confirmLongOrgName(actionLabel);
    } finally {
      window.setTimeout(() => {
        confirmLockRef.current = false;
      }, 400);
    }
  }

  function goBackFromCredentials() {
    setStep(usage === "personal" ? 1 : 2);
    setFieldErrors({});
  }

  async function handleCreateAccount() {
    setApiError(null);
    setSuggestLogin(false);

    const credentialErrors = validateRegisterCredentials(
      username,
      email,
      password,
      confirmPassword,
      validateUsernameClient,
    );
    const teamErrors =
      usage === "team"
        ? validateRegisterTeamRole({ teamRole, orgName, inviteCode })
        : {};
    const errors = { ...credentialErrors, ...teamErrors };
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (
      usage === "team" &&
      teamRole === "creator" &&
      needsLongOrgNameConfirm(orgName) &&
      !runLongNameConfirm("创建账号")
    ) {
      return;
    }

    const accountType = usage === "team" ? "enterprise" : "personal";
    const memberInviteCode =
      usage === "team" && teamRole === "member" ? inviteCode.trim() : undefined;

    setLoading(true);
    try {
      const session = await registerAndLogin(
        email.trim(),
        username.trim(),
        password,
        accountType,
        accountType === "enterprise" && teamRole === "creator"
          ? orgName.trim()
          : undefined,
        nickname.trim() || undefined,
        memberInviteCode,
      );
      applySession(session);

      if (usage === "team" && session.user.org_id) {
        setStoredWorkspace(session.user.org_id);
      }

      navigate(redirectTo, { replace: true });
    } catch (err) {
      const rawMessage =
        err instanceof Error ? err.message : "操作失败，请稍后重试";
      const message = rawMessage.includes("邀请码")
        ? INVITE_INVALID_MSG
        : rawMessage;
      setApiError(message);
      if (message.includes("已注册") || message.includes("已被使用")) {
        setSuggestLogin(true);
      }
      if (rawMessage.includes("邀请码")) {
        setFieldErrors((prev) => ({
          ...prev,
          inviteCode: "邀请码无效或已过期",
        }));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[420px] flex-1 flex-col">
      <div className="shrink-0">
        <RegisterStepsIndicator step={step} usage={usage} />
      </div>

      {apiError && (
        <div className="mb-3 mt-3 shrink-0">
          <AuthFormAlert
            message={apiError}
            action={
              suggestLogin
                ? {
                    label: "已有账号，去登录",
                    onClick: onSwitchToLogin,
                  }
                : undefined
            }
          />
        </div>
      )}

      {step === 1 && (
        <div className="flex min-h-0 flex-1 flex-col">
          <RegisterUsageStep
            usage={usage}
            onSelectUsage={handleSelectUsage}
            onContinue={goUsageContinue}
          />
        </div>
      )}

      {step === 2 && usage === "team" && (
        <div className="flex min-h-0 flex-1 flex-col">
          <RegisterTeamRoleStep
            teamRole={teamRole}
            orgName={orgName}
            inviteCode={inviteCode}
            fieldErrors={fieldErrors}
            onSelectRole={handleSelectRole}
            onOrgNameChange={(v) => {
              setOrgName(v);
              clearFieldError("orgName");
            }}
            onInviteCodeChange={(v) => {
              setInviteCode(v);
              setResolvedOrgName("");
              clearFieldError("inviteCode");
            }}
            onBack={() => {
              setStep(1);
              setFieldErrors({});
            }}
            onContinue={() => {
              void goTeamContinue();
            }}
            canContinue={canContinueTeamStep(teamRole, orgName, inviteCode)}
            continueLoading={validatingInvite}
          />
        </div>
      )}

      {step === 3 && usage && (
        <div className="flex min-h-0 flex-1 flex-col">
          <RegisterCredentialsStep
            usage={usage}
            teamRole={teamRole}
            orgName={orgName}
            inviteCode={inviteCode}
            resolvedOrgName={resolvedOrgName}
            username={username}
            email={email}
            nickname={nickname}
            showNickname={showNickname}
            password={password}
            confirmPassword={confirmPassword}
            fieldErrors={fieldErrors}
            loading={loading}
            onUsernameChange={(v) => {
              setUsername(v);
              clearFieldError("username");
            }}
            onEmailChange={(v) => {
              setEmail(v);
              clearFieldError("email");
            }}
            onNicknameChange={setNickname}
            onShowNickname={() => setShowNickname(true)}
            onPasswordChange={(v) => {
              setPassword(v);
              clearFieldError("password");
            }}
            onConfirmPasswordChange={(v) => {
              setConfirmPassword(v);
              clearFieldError("confirmPassword");
            }}
            onBack={goBackFromCredentials}
            onSubmit={handleCreateAccount}
          />
        </div>
      )}
    </div>
  );
}
