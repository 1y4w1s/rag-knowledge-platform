import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/lib/auth-context";
import { DepartmentProvider } from "@/lib/department-context";
import { WorkspaceProvider } from "@/lib/workspace-context";

export function ProtectedRoute() {
  const location = useLocation();
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    const redirect = encodeURIComponent(
      `${location.pathname}${location.search}`,
    );
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  return (
    <WorkspaceProvider>
      <DepartmentProvider>
        <Outlet />
      </DepartmentProvider>
    </WorkspaceProvider>
  );
}
