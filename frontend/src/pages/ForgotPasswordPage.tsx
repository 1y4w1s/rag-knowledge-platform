import { useState } from "react";
import { Link } from "react-router-dom";

import { AuthCard, AuthCardBrand } from "@/components/auth/AuthCard";
import { AuthFormAlert } from "@/components/auth/AuthField";
import { Button } from "@/components/ui/button";
import { forgotPassword } from "@/lib/auth-api";
import { useTheme } from "@/lib/use-theme";

export function ForgotPasswordPage() {
  const { theme, toggleTheme } = useTheme();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await forgotPassword(email.trim());
      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "请求失败，请稍后重试");
    } finally {
      setLoading(false);
    }
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

        {sent ? (
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
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            </div>
            <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
              邮件已发送
            </h2>
            <p className="max-w-sm text-[13px] leading-relaxed text-[var(--auth-muted)]">
              如果该邮箱已注册，您将收到一封包含密码重置链接的邮件。请检查收件箱（及垃圾邮件）。
            </p>
            <Link
              to="/login"
              className="mt-2 text-sm font-semibold text-[var(--auth-action)] underline-offset-2 hover:underline"
            >
              返回登录
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-1 flex-col">
            <div className="mb-7">
              <h2 className="font-serif text-2xl font-bold text-[var(--auth-text)]">
                重置密码
              </h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--auth-muted)]">
                输入注册时使用的邮箱，我们将发送重置链接。
              </p>
            </div>

            {error && (
              <div className="mb-4">
                <AuthFormAlert message={error} />
              </div>
            )}

            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="text-[13px] font-medium text-[var(--auth-text)]"
              >
                邮箱
              </label>
              <input
                id="email"
                type="email"
                required
                autoFocus
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="auth-input h-11 w-full rounded-[8px] border border-[var(--auth-line)] bg-[var(--auth-field-bg)] px-3 text-sm text-[var(--auth-text)] outline-none placeholder:text-[#B5A8A2] focus-visible:border-[var(--auth-action)] focus-visible:ring-2 focus-visible:ring-[rgb(203_107_61/0.14)]"
              />
            </div>

            <div className="mt-8 space-y-3">
              <Button
                type="submit"
                variant="brandGrad"
                className="h-11 w-full"
                disabled={loading || !email.trim()}
              >
                {loading ? "发送中…" : "发送重置邮件"}
              </Button>
              <p className="text-center text-[13px] text-[var(--auth-muted)]">
                记起密码了？{" "}
                <Link
                  to="/login"
                  className="font-semibold text-[var(--auth-action)] underline-offset-2 hover:underline"
                >
                  返回登录
                </Link>
              </p>
            </div>
          </form>
        )}
      </AuthCard>

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
    </div>
  );
}
