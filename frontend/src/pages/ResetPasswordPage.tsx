import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { AuthCard, AuthCardBrand } from "@/components/auth/AuthCard";
import { AuthFormAlert } from "@/components/auth/AuthField";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/use-theme";

const API_BASE = "/api/v1";

const fieldClassName =
  "auth-input h-11 w-full rounded-[8px] border border-[var(--auth-line)] bg-[var(--auth-field-bg)] px-3 text-sm text-[var(--auth-text)] outline-none placeholder:text-[#B5A8A2] focus-visible:border-[var(--auth-action)] focus-visible:ring-2 focus-visible:ring-[rgb(203_107_61/0.14)]";

export function ResetPasswordPage() {
  const { theme, toggleTheme } = useTheme();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("重置链接无效：缺少令牌");
      return;
    }
    if (password.length < 8) {
      setError("密码至少 8 位");
      return;
    }
    if (password !== confirm) {
      setError("两次密码输入不一致");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(data.detail ?? "重置失败，链接可能已过期");
      }
      setDone(true);
      setTimeout(() => navigate("/login?notice=password-changed"), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "重置失败");
    } finally {
      setLoading(false);
    }
  }

  const themeFab = (
    <button
      type="button"
      onClick={toggleTheme}
      className="theme-fab"
      aria-label={theme === "dark" ? "切换到暖白主题" : "切换到暗色主题"}
      title={theme === "dark" ? "切换到暖白主题" : "切换到暗色主题"}
    >
      {theme === "dark" ? (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.5v2.4M12 19.1v2.4M4.6 4.6l1.7 1.7M17.7 17.7l1.7 1.7M2.5 12h2.4M19.1 12h2.4M4.6 19.4l1.7-1.7M17.7 6.3l1.7-1.7" />
        </svg>
      ) : (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20 14.5A8 8 0 0 1 9.5 4 7 7 0 1 0 20 14.5z" />
        </svg>
      )}
    </button>
  );

  if (!token) {
    return (
      <div
        className="auth-page relative flex min-h-screen items-center justify-center px-6 py-12"
        data-theme={theme}
        style={{
          backgroundColor: "var(--auth-bg)",
          backgroundImage: "var(--auth-wash)",
        }}
      >
        <AuthCard>
          <AuthCardBrand />
          <div className="flex flex-1 flex-col items-center justify-center gap-4 pt-6 text-center">
            <p className="text-[13px] text-[var(--auth-muted)]">
              重置链接无效：缺少安全令牌。
            </p>
            <Link
              to="/forgot-password"
              className="text-sm font-semibold text-[var(--auth-action)] underline-offset-2 hover:underline"
            >
              重新发送重置邮件
            </Link>
          </div>
        </AuthCard>
        {themeFab}
      </div>
    );
  }

  return (
    <div
      className="auth-page relative flex min-h-screen items-center justify-center px-6 py-12"
      data-theme={theme}
      style={{
        backgroundColor: "var(--auth-bg)",
        backgroundImage: "var(--auth-wash)",
      }}
    >
      <AuthCard>
        <AuthCardBrand />

        {done ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 pt-6 text-center">
            <div
              className="flex h-11 w-11 items-center justify-center rounded-full"
              style={{
                backgroundColor:
                  "color-mix(in srgb, var(--auth-action) 14%, transparent)",
                color: "var(--ok)",
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M20 6L9 17L4 12" />
              </svg>
            </div>
            <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
              密码已重置
            </h2>
            <p className="text-[13px] text-[var(--auth-muted)]">
              正在跳转至登录页…
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-1 flex-col">
            <div className="mb-7">
              <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
                设置新密码
              </h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--auth-muted)]">
                请输入新密码（至少 8 位）。
              </p>
            </div>

            {error && (
              <div className="mb-4">
                <AuthFormAlert message={error} />
              </div>
            )}

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="new-password"
                  className="text-[13px] font-medium text-[var(--auth-text)]"
                >
                  新密码
                </label>
                <input
                  id="new-password"
                  type="password"
                  required
                  autoFocus
                  minLength={8}
                  placeholder="至少 8 位"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={fieldClassName}
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="confirm-password"
                  className="text-[13px] font-medium text-[var(--auth-text)]"
                >
                  确认密码
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  minLength={8}
                  placeholder="再次输入新密码"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className={fieldClassName}
                />
              </div>
            </div>

            <div className="mt-8">
              <Button
                type="submit"
                variant="brandGrad"
                className="h-11 w-full"
                disabled={loading || !password || !confirm}
              >
                {loading ? "重置中…" : "重置密码"}
              </Button>
            </div>
          </form>
        )}
      </AuthCard>

      {themeFab}
    </div>
  );
}
