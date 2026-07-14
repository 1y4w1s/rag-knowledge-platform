import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { LoginAuthForm } from "@/components/auth/LoginAuthForm";
import { useAuth } from "@/lib/auth-context";

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

  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, navigate, redirectTo]);

  return (
    <div
      className="auth-page flex min-h-screen items-center justify-center px-6 py-12"
      style={{
        backgroundColor: "var(--auth-bg)",
        backgroundImage: "var(--auth-wash)",
      }}
    >
      <LoginAuthForm />
    </div>
  );
}
