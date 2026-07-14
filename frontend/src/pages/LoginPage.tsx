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
  const { theme, toggleTheme } = useTheme();

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
