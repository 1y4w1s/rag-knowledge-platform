import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { LoginAuthForm } from "@/components/auth/LoginAuthForm";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/lib/use-theme";

function safeRedirect(path: string | null): string {
  if (!path || !path.startsWith("/") || path.startsWith("//")) {
    return "/dashboard";
  }
  return path;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuth();
  const redirectTo = safeRedirect(searchParams.get("redirect"));
  const { theme, mode, toggleTheme } = useTheme();

  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, navigate, redirectTo]);


  return (
    <div
      className="auth-page relative flex min-h-screen items-center justify-center px-6 py-12"
      data-theme={theme}
      style={{
        backgroundColor: "var(--auth-bg)",
        backgroundImage: "var(--auth-wash)",
      }}
    >
      <LoginAuthForm />

      <button
        type="button"
        onClick={toggleTheme}
        className="theme-fab"
        aria-label={
          mode === "dark"
            ? "切换到暖白主题"
            : mode === "system"
              ? "切换到暗色（当前跟随系统）"
              : "切换到跟随系统"
        }
        title={
          mode === "dark"
            ? "切换到暖白主题"
            : mode === "system"
              ? "切换到暗色（当前跟随系统）"
              : "切换到跟随系统"
        }
      >
        {mode === "system" ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        ) : theme === "dark" ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
          </svg>
        )}
      </button>
    </div>
  );
}
