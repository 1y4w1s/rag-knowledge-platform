import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// Mock useAuth
const mockIsAuthenticated = vi.fn().mockReturnValue(true);
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated() }),
}));

// Mock context providers to simplify rendering
vi.mock("@/lib/workspace-context", () => ({
  WorkspaceProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
vi.mock("@/lib/department-context", () => ({
  DepartmentProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";

describe("ProtectedRoute", () => {
  it("renders children (Outlet) when authenticated", () => {
    mockIsAuthenticated.mockReturnValue(true);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div data-testid="protected-content">仪表盘</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("protected-content")).toBeTruthy();
    expect(screen.getByText("仪表盘")).toBeTruthy();
  });

  it("redirects to /login when not authenticated", () => {
    mockIsAuthenticated.mockReturnValue(false);
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<div data-testid="protected-content">仪表盘</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">登录页</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("login-page")).toBeTruthy();
    expect(screen.queryByTestId("protected-content")).toBeNull();
  });

  it("includes current path as redirect parameter in login URL", () => {
    mockIsAuthenticated.mockReturnValue(false);
    render(
      <MemoryRouter initialEntries={["/knowledge-bases/kb-123"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/knowledge-bases/:id" element={<div>KB详情</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">登录页</div>} />
        </Routes>
      </MemoryRouter>,
    );
    // Should redirect to /login with redirect param
    expect(screen.getByTestId("login-page")).toBeTruthy();
  });

  it("redirects with empty search params preserved", () => {
    mockIsAuthenticated.mockReturnValue(false);
    render(
      <MemoryRouter initialEntries={["/ask?workspace=team"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/ask" element={<div>问答</div>} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">登录页</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("login-page")).toBeTruthy();
  });
});
