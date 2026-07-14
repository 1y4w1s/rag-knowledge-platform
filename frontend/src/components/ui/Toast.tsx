import { useCallback, useEffect, useState } from "react";
import { X } from "lucide-react";

const DEFAULT_DURATION_MS = 4000;

interface ToastState {
  message: string;
  key: number;
}

export function useToast() {
  const [toast, setToast] = useState<ToastState | null>(null);

  const dismiss = useCallback(() => {
    setToast(null);
  }, []);

  const show = useCallback((message: string) => {
    setToast({ message, key: Date.now() });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(dismiss, DEFAULT_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [toast, dismiss]);

  return { toast, show, dismiss };
}

interface ToastProps {
  message: string | null;
  onDismiss: () => void;
}

export function Toast({ message, onDismiss }: ToastProps) {
  if (!message) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 left-1/2 z-[200] flex w-[min(24rem,calc(100vw-2rem))] -translate-x-1/2 items-start gap-2 rounded-xl border border-[var(--line2)] bg-white px-4 py-3 shadow-md"
    >
      <p className="flex-1 text-sm text-foreground">{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 rounded p-0.5 text-muted hover:text-foreground"
        aria-label="关闭提示"
      >
        <X className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
