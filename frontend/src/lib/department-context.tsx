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
import { alignDepartmentWithUser } from "@/lib/department-align";
import {
  DEPARTMENT_ALL,
  getStoredDepartmentId,
  readDepartmentIdForWorkspace,
  setStoredDepartmentId,
  type DepartmentScopeId,
} from "@/lib/department-storage";
import { useWorkspace } from "@/lib/workspace-context";
import type { WorkspaceId } from "@/lib/workspace-storage";

const DEPARTMENT_RESET_TOAST = "部门已重置";
const DEPARTMENT_SCOPE_TOAST = "已切换部门，检索范围已更新";
const SHELL_TOAST_MS = 4000;

interface DepartmentContextValue {
  /** API query 用；个人空间恒为 null */
  departmentId: string | null;
  generation: number;
  /** 侧栏部门选择器 refetch 代际（ORG CRUD 后 bump） */
  pickerGeneration: number;
  getGeneration: () => number;
  isTeamDepartmentActive: boolean;
  isAllScope: boolean;
  shellToast: string | null;
  dismissShellToast: () => void;
  setDepartment: (next: DepartmentScopeId) => void;
  resetDepartment: (options?: { toast?: boolean }) => void;
  invalidateDepartmentPicker: () => void;
}

const DepartmentContext = createContext<DepartmentContextValue | null>(null);

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

function DepartmentShellToast({
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

function activeDepartmentForWorkspace(
  workspace: WorkspaceId,
  resolvedId: string | null,
): string | null {
  if (workspace === "personal") return null;
  return resolvedId;
}

export function DepartmentProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, refreshUserFromServer } = useAuth();
  const { workspace, isTeamWorkspace } = useWorkspace();
  const [departmentId, setDepartmentIdState] = useState<string | null>(() =>
    activeDepartmentForWorkspace(
      workspace,
      readDepartmentIdForWorkspace(workspace),
    ),
  );
  const [generation, setGeneration] = useState(0);
  const [pickerGeneration, setPickerGeneration] = useState(0);
  const [shellToast, setShellToast] = useState<string | null>(null);
  const generationRef = useRef(0);
  const departmentRef = useRef(departmentId);
  const workspaceRef = useRef(workspace);

  useEffect(() => {
    departmentRef.current = departmentId;
  }, [departmentId]);

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

  const invalidateDepartmentPicker = useCallback(() => {
    setPickerGeneration((g) => g + 1);
  }, []);

  const applyResolvedDepartment = useCallback(
    (
      nextId: string | null,
      options?: { bump?: boolean; persistOrgId?: string },
    ) => {
      const active = activeDepartmentForWorkspace(workspaceRef.current, nextId);
      const changed = departmentRef.current !== active;
      departmentRef.current = active;
      setDepartmentIdState(active);
      if (options?.persistOrgId && nextId) {
        setStoredDepartmentId(options.persistOrgId, nextId);
      }
      if (options?.bump && changed) {
        bumpGenerationRef(generationRef, setGeneration);
      }
    },
    [],
  );

  const resetDepartment = useCallback(
    (options?: { toast?: boolean }) => {
      if (!user || workspaceRef.current === "personal") {
        applyResolvedDepartment(null);
        return;
      }
      const aligned = alignDepartmentWithUser(null, user);
      if (!aligned.ok) {
        applyResolvedDepartment(null, { bump: true });
        return;
      }
      setStoredDepartmentId(workspaceRef.current, aligned.departmentId);
      applyResolvedDepartment(aligned.departmentId, { bump: true });
      if (options?.toast !== false) {
        showShellToast(DEPARTMENT_RESET_TOAST);
      }
      window.requestAnimationFrame(() => {
        navigate("/dashboard", { replace: true });
      });
    },
    [user, applyResolvedDepartment, navigate, showShellToast],
  );

  const setDepartment = useCallback(
    (next: DepartmentScopeId) => {
      if (workspaceRef.current === "personal") return;
      if (!user) return;
      if (departmentRef.current === next) return;

      const aligned = alignDepartmentWithUser(next, user);
      if (!aligned.ok) {
        resetDepartment();
        return;
      }

      const orgId = workspaceRef.current;
      setStoredDepartmentId(orgId, aligned.departmentId);
      applyResolvedDepartment(aligned.departmentId, { bump: true });
      showShellToast(DEPARTMENT_SCOPE_TOAST);
    },
    [user, applyResolvedDepartment, resetDepartment, showShellToast],
  );

  const runAlign = useCallback(
    (userOverride?: StoredUser | null) => {
      const effectiveUser = userOverride ?? user;
      const currentWorkspace = workspaceRef.current;

      if (currentWorkspace === "personal") {
        applyResolvedDepartment(null);
        return;
      }

      if (!effectiveUser) {
        applyResolvedDepartment(null);
        return;
      }

      const stored = getStoredDepartmentId(currentWorkspace);
      const aligned = alignDepartmentWithUser(stored, effectiveUser);

      if (!aligned.ok) {
        applyResolvedDepartment(null, { bump: true });
        if (stored) {
          showShellToast(DEPARTMENT_RESET_TOAST);
        }
        return;
      }

      if (aligned.realigned || stored !== aligned.departmentId) {
        setStoredDepartmentId(currentWorkspace, aligned.departmentId);
        if (stored && aligned.realigned) {
          showShellToast(DEPARTMENT_RESET_TOAST);
        }
      }

      const prev = departmentRef.current;
      applyResolvedDepartment(aligned.departmentId, {
        bump: prev !== aligned.departmentId,
        persistOrgId: currentWorkspace,
      });
    },
    [user, applyResolvedDepartment, showShellToast],
  );

  useEffect(() => {
    runAlign();
  }, [
    workspace,
    user?.id,
    user?.primary_unit_id,
    user?.unit_ids?.join(","),
    runAlign,
  ]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      if (workspaceRef.current === "personal") return;
      void refreshUserFromServer().then((freshUser) => {
        if (freshUser) runAlign(freshUser);
      });
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [refreshUserFromServer, runAlign]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (
      window as Window & {
        __zhianSetDepartment?: (next: DepartmentScopeId) => void;
      }
    ).__zhianSetDepartment = setDepartment;
    return () => {
      delete (
        window as Window & {
          __zhianSetDepartment?: (next: DepartmentScopeId) => void;
        }
      ).__zhianSetDepartment;
    };
  }, [setDepartment]);

  const value = useMemo<DepartmentContextValue>(
    () => ({
      departmentId,
      generation,
      pickerGeneration,
      getGeneration,
      isTeamDepartmentActive:
        isTeamWorkspace && departmentId !== null,
      isAllScope: departmentId === DEPARTMENT_ALL,
      shellToast,
      dismissShellToast,
      setDepartment,
      resetDepartment,
      invalidateDepartmentPicker,
    }),
    [
      departmentId,
      generation,
      pickerGeneration,
      getGeneration,
      isTeamWorkspace,
      shellToast,
      dismissShellToast,
      setDepartment,
      resetDepartment,
      invalidateDepartmentPicker,
    ],
  );

  return (
    <DepartmentContext.Provider value={value}>
      {children}
      <DepartmentShellToast
        message={shellToast}
        onDismiss={dismissShellToast}
      />
    </DepartmentContext.Provider>
  );
}

export function useDepartment(): DepartmentContextValue {
  const ctx = useContext(DepartmentContext);
  if (!ctx) {
    throw new Error("useDepartment must be used within DepartmentProvider");
  }
  return ctx;
}
