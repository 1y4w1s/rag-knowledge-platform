import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface ShellBreadcrumbContextValue {
  override: ReactNode | null;
  setOverride: (node: ReactNode | null) => void;
}

const ShellBreadcrumbContext = createContext<ShellBreadcrumbContextValue | null>(
  null,
);

export function ShellBreadcrumbProvider({ children }: { children: ReactNode }) {
  const [override, setOverride] = useState<ReactNode | null>(null);
  const value = useMemo(
    () => ({ override, setOverride }),
    [override],
  );
  return (
    <ShellBreadcrumbContext.Provider value={value}>
      {children}
    </ShellBreadcrumbContext.Provider>
  );
}

export function useShellBreadcrumb(): ShellBreadcrumbContextValue {
  const ctx = useContext(ShellBreadcrumbContext);
  if (!ctx) {
    throw new Error("useShellBreadcrumb must be used within ShellBreadcrumbProvider");
  }
  return ctx;
}
