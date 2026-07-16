import { lazy, Suspense, useState } from "react";

import { useNavigate, useSearchParams } from "react-router-dom";



import {

  AuthCard,

  AuthCardBody,

  AuthCardBrand,

} from "@/components/auth/AuthCard";

import { AuthField, AuthFormAlert } from "@/components/auth/AuthField";

import {

  AuthSegmentedTabs,

  type AuthTab,

} from "@/components/auth/AuthSegmentedTabs";

// 注册表单仅在切到「注册」tab 时渲染：懒加载以移出登录入口 chunk，降低首屏 JS / TBT。
const RegisterForm = lazy(() =>
  import("@/components/auth/RegisterForm").then((m) => ({ default: m.RegisterForm })),
);

import { Button } from "@/components/ui/button";

import { login } from "@/lib/auth-api";

import { useAuth } from "@/lib/auth-context";

import {

  FORGOT_PASSWORD_HINT,

} from "@/lib/auth-env";

import { type FieldErrors, validateLoginFields } from "@/lib/auth-form-validation";



function safeRedirect(path: string | null): string {

  if (!path || !path.startsWith("/") || path.startsWith("//")) {

    return "/dashboard";

  }

  return path;

}



export function LoginAuthForm() {

  const navigate = useNavigate();

  const [searchParams] = useSearchParams();

  const { applySession } = useAuth();

  const redirectTo = safeRedirect(searchParams.get("redirect"));

  const passwordChangedNotice =

    searchParams.get("notice") === "password-changed"

      ? "密码已更新，请使用新密码登录"

      : null;



  const [tab, setTab] = useState<AuthTab>("login");

  const [identifier, setIdentifier] = useState("");

  const [password, setPassword] = useState("");

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const [apiError, setApiError] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  const [forgotHintVisible, setForgotHintVisible] = useState(false);



  function switchTab(next: AuthTab) {

    setTab(next);

    setFieldErrors({});

    setApiError(null);

    setForgotHintVisible(false);

  }



  function clearFieldError(key: string) {

    setFieldErrors((prev) => {

      if (!prev[key]) return prev;

      const next = { ...prev };

      delete next[key];

      return next;

    });

  }



  async function finishLogin(idValue: string, passwordValue: string) {

    const session = await login(idValue, passwordValue);

    applySession(session);

    navigate(redirectTo, { replace: true });

  }



  async function handleLoginSubmit(event: React.FormEvent) {

    event.preventDefault();

    setApiError(null);



    const errors = validateLoginFields(identifier, password);

    setFieldErrors(errors);

    if (Object.keys(errors).length > 0) return;



    setLoading(true);

    try {

      await finishLogin(identifier.trim(), password);

    } catch (err) {

      setApiError(err instanceof Error ? err.message : "操作失败，请稍后重试");

    } finally {

      setLoading(false);

    }

  }



  return (

    <AuthCard>

      <AuthCardBrand />

      <AuthSegmentedTabs active={tab} onChange={switchTab} />



      <AuthCardBody>

        {tab === "register" ? (

          <Suspense

            fallback={

              <div className="flex justify-center py-10" role="status">

                <span

                  className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--line2)] border-t-[var(--action)]"

                  aria-hidden="true"

                />

                <span className="sr-only">加载注册表单…</span>

              </div>

            }

          >

            <RegisterForm

              redirectTo={redirectTo}

              onSwitchToLogin={() => switchTab("login")}

            />

          </Suspense>

        ) : (

          <form

            noValidate

            onSubmit={handleLoginSubmit}

            className="flex flex-1 flex-col"

          >

            <div className="mb-6">

              <h2 className="font-serif text-xl font-semibold text-[var(--auth-text)]">

                欢迎回来

              </h2>

              <p className="mt-1.5 text-sm text-[var(--auth-muted)]">

                使用邮箱或用户名登录。

              </p>

            </div>



            {passwordChangedNotice && (

              <div

                role="status"

                className="mb-4 rounded-md border border-[color:#d4ccc4] bg-[color:var(--status-ok-bg)] px-3 py-2 text-sm text-[color:var(--status-ok-text)]"

              >

                {passwordChangedNotice}

              </div>

            )}



            {apiError && (

              <div className="mb-4">

                <AuthFormAlert message={apiError} />

              </div>

            )}



            <div className="flex flex-1 flex-col justify-center space-y-3.5">

              <AuthField

                id="identifier"

                label="邮箱或用户名"

                autoComplete="username"

                value={identifier}

                onChange={(v) => {

                  setIdentifier(v);

                  clearFieldError("identifier");

                }}

                placeholder="name@company.com 或 zhangsan"

                error={fieldErrors.identifier}

              />

              <div>

                <AuthField

                  id="password"

                  label="密码"

                  type="password"

                  autoComplete="current-password"

                  value={password}

                  onChange={(v) => {

                    setPassword(v);

                    clearFieldError("password");

                  }}

                  placeholder="至少 8 位"

                  error={fieldErrors.password}

                  showPasswordToggle

                />

                <div className="mt-1.5 text-right">

                  <button

                    type="button"

                    className="text-xs text-[var(--auth-muted)] underline-offset-2 hover:text-[var(--auth-action)] hover:underline"

                    onClick={() => setForgotHintVisible(true)}

                  >

                    忘记密码？

                  </button>

                </div>

                {forgotHintVisible && (

                  <p

                    role="status"

                    className="mt-1.5 text-right text-xs leading-relaxed text-[var(--auth-muted)]"

                  >

                    {FORGOT_PASSWORD_HINT}

                  </p>

                )}

              </div>

            </div>



            <div className="mt-auto space-y-4 pt-6">

              <Button

                type="submit"

                variant="brandGrad"

                className="w-full"

                disabled={loading}

              >

                {loading ? "提交中…" : "登录"}

              </Button>

            </div>

          </form>

        )}

      </AuthCardBody>

    </AuthCard>

  );

}

