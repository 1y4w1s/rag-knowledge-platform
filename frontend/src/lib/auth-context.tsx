import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { fetchCurrentUser, type AuthSession } from "@/lib/auth-api";
import {
  clearAuthSession,
  getAccessToken,
  getStoredUser,
  isAuthenticated as checkAuthenticated,
  saveAuthSession,
  type StoredUser,
} from "@/lib/auth-storage";
import { clearAllDepartmentKeys } from "@/lib/department-storage";
import {
  clearWorkspaceAndRecentKeys,
  prepareWorkspaceForLogin,
} from "@/lib/workspace-storage";

interface AuthContextValue {
  user: StoredUser | null;
  isAuthenticated: boolean;
  isOrgAdmin: boolean;
  applySession: (session: AuthSession) => void;
  logout: () => void;
  syncFromStorage: () => void;
  /** WS-2-1 E8：Tab 重新可见时与 `/me` 对齐后再跑 workspace align */
  refreshUserFromServer: () => Promise<StoredUser | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(() => getStoredUser());

  const syncFromStorage = useCallback(() => {
    setUser(getStoredUser());
  }, []);

  const applySession = useCallback((session: AuthSession) => {
    prepareWorkspaceForLogin();
    clearAllDepartmentKeys();
    setUser(session.user);
  }, []);

  const logout = useCallback(() => {
    clearWorkspaceAndRecentKeys();
    clearAllDepartmentKeys();
    clearAuthSession();
    setUser(null);
  }, []);

  const refreshUserFromServer = useCallback(async (): Promise<StoredUser | null> => {
    if (!checkAuthenticated()) return null;
    try {
      const freshUser = await fetchCurrentUser();
      const token = getAccessToken();
      if (token) saveAuthSession(token, freshUser);
      setUser(freshUser);
      return freshUser;
    } catch {
      clearAuthSession();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    if (!checkAuthenticated()) return;

    void refreshUserFromServer();
  }, [refreshUserFromServer]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: checkAuthenticated() && user !== null,
      isOrgAdmin:
        user?.account_type === "enterprise" && user.org_role === "admin",
      applySession,
      logout,
      syncFromStorage,
      refreshUserFromServer,
    }),
    [user, applySession, logout, syncFromStorage, refreshUserFromServer],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export function getAccountTypeLabel(user: StoredUser): string {
  if (user.account_type === "personal") return "个人版";
  if (user.org_role === "admin") return "团队管理员";
  if (user.org_role === "member") return "团队成员";
  return "团队版";
}

export function getDisplayName(user: StoredUser): string {
  if (user.nickname?.trim()) return user.nickname.trim();
  return user.username;
}

export function getDisplayEmail(user: StoredUser): string {
  return getDisplayName(user);
}
