import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

const MOBILE_MQ = "(max-width: 768px)";

interface MobileDrawerContextValue {
  isOpen: boolean;
  toggle: () => void;
  close: () => void;
}

const MobileDrawerContext = createContext<MobileDrawerContextValue | null>(null);

export function MobileDrawerProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_MQ);
    const onChange = () => {
      if (!mq.matches) setIsOpen(false);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen]);

  const close = useCallback(() => setIsOpen(false), []);
  const toggle = useCallback(() => setIsOpen((open) => !open), []);

  return (
    <MobileDrawerContext.Provider value={{ isOpen, toggle, close }}>
      {children}
    </MobileDrawerContext.Provider>
  );
}

export function useMobileDrawer(): MobileDrawerContextValue {
  const ctx = useContext(MobileDrawerContext);
  if (!ctx) {
    throw new Error("useMobileDrawer must be used within MobileDrawerProvider");
  }
  return ctx;
}
