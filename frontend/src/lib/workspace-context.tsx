import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type ReactNode,
  type SetStateAction,
} from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

import { Toast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth-context";
import type { StoredUser } from "@/lib/auth-storage";
import { alignWorkspaceWithUser } from "@/lib/workspace-align";
import { registerWorkspaceApiReset } from "@/lib/workspace-api-reset";
import {
  getStoredWorkspace,
  migrateLegacyRecentKbKey,
  setStoredWorkspace,
  type WorkspaceId,
} from "@/lib/workspace-storage";

const WORKSPACE_RESET_TOAST = "工作区已重置";
const SHELL_TOAST_MS = 4000;

interface WorkspaceContextValue {
  workspace: WorkspaceId;
  generation: number;
  getGeneration: () => number;
  isTeamWorkspace: boolean;
  shellToast: string | null;
  dismissShellToast: () => void;
  redirectWithGuardToast: (message: string, to?: string) => void;
  setWorkspace: (next: WorkspaceId) => void;
  resetToPersonal: (options?: { toast?: boolean }) => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function bumpGenerationRef(
  generationRef: MutableRefObject<number>,
  setGeneration: Dispatch<SetStateAction<number>>,
): void {
  setGeneration((g) => {
    const next = g + 1;
    generationRef.current = next;
    return next;
  });
}

function WorkspaceShellToast({
  message,
  onDismiss,
}: {
  message: string | null;
  onDismiss: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onDismiss, SHELL_TOAST_MS);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  return createPortal(
    <Toast message={message} onDismiss={onDismiss} />,
    document.body,
  );
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, refreshUserFromServer } = useAuth();
  const [workspace, setWorkspaceState] = useState<WorkspaceId>(() =>
    getStoredWorkspace(),
  );
  const [generation, setGeneration] = useState(0);
  const [shellToast, setShellToast] = useState<string | null>(null);
  const generationRef = useRef(0);
  const workspaceRef = useRef(workspace);

  useEffect(() => {
    workspaceRef.current = workspace;
  }, [workspace]);

  useEffect(() => {
    generationRef.current = generation;
  }, [generation]);

  const getGeneration = useCallback(() => generationRef.current, []);

  const dismissShellToast = useCallback(() => {
    setShellToast(null);
  }, []);

  const showShellToast = useCallback((message: string) => {
    setShellToast(message);
  }, []);

  const redirectWithGuardToast = useCallback(
    (message: string, to = "/dashboard") => {
      showShellToast(message);
      window.requestAnimationFrame(() => {
        navigate(to, { replace: true });
      });
    },
    [navigate, showShellToast],
  );

  const resetToPersonal = useCallback(
    (options?: { toast?: boolean }) => {
      setStoredWorkspace("personal");
      workspaceRef.current = "personal";
      setWorkspaceState("personal");
      bumpGenerationRef(generationRef, setGeneration);
      if (options?.toast !== false) {
        showShellToast(WORKSPACE_RESET_TOAST);
      }
      navigate("/dashboard", { replace: true });
    },
    [navigate, showShellToast],
  );

  const setWorkspace = useCallback(
    (next: WorkspaceId) => {
      if (workspaceRef.current === next) return;
      setStoredWorkspace(next);
      workspaceRef.current = next;
      setWorkspaceState(next);
      bumpGenerationRef(generationRef, setGeneration);
      navigate("/dashboard", { replace: true });
    },
    [navigate],
  );

  const runAlign = useCallback(
    (userOverride?: StoredUser | null) => {
      const effectiveUser = userOverride ?? user;
      if (!effectiveUser) return;

      migrateLegacyRecentKbKey();
      const stored = getStoredWorkspace();
      const aligned = alignWorkspaceWithUser(stored, effectiveUser);

      if (!aligned.ok) {
        resetToPersonal();
        return;
      }

      setWorkspaceState((current) => {
        if (current === aligned.workspace) return current;
        setStoredWorkspace(aligned.workspace);
        workspaceRef.current = aligned.workspace;
        bumpGenerationRef(generationRef, setGeneration);
        return aligned.workspace;
      });
    },
    [user, resetToPersonal],
  );

  useEffect(() => {
    if (!user) return;
    runAlign();
  }, [user?.id, user?.org_id, runAlign]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      void refreshUserFromServer().then((freshUser) => {
        if (freshUser) runAlign(freshUser);
      });
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshUserFromServer, runAlign]);

  useEffect(() => {
    registerWorkspaceApiReset(() => resetToPersonal());
    return () => registerWorkspaceApiReset(() => {});
  }, [resetToPersonal]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (
      window as Window & { __zhianSetWorkspace?: (next: WorkspaceId) => void }
    ).__zhianSetWorkspace = setWorkspace;
    return () => {
      delete (
        window as Window & { __zhianSetWorkspace?: (next: WorkspaceId) => void }
      ).__zhianSetWorkspace;
    };
  }, [setWorkspace]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspace,
      generation,
      getGeneration,
      isTeamWorkspace: workspace !== "personal",
      shellToast,
      dismissShellToast,
      redirectWithGuardToast,
      setWorkspace,
      resetToPersonal,
    }),
    [
      workspace,
      generation,
      getGeneration,
      shellToast,
      dismissShellToast,
      redirectWithGuardToast,
      setWorkspace,
      resetToPersonal,
    ],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
      <WorkspaceShellToast
        message={shellToast}
        onDismiss={dismissShellToast}
      />
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  }
  return ctx;
}
