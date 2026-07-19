import type { AgentMode } from "@/lib/agent-mode";
import { cn } from "@/lib/utils";

interface AgentModeSwitcherProps {
  value: AgentMode;
  onChange: (mode: AgentMode) => void;
  /** 外部禁用（如权限不足）；发送中仍可切换并 Abort SSE（G3-E1） */
  disabled?: boolean;
  className?: string;
}

const MODES: { value: AgentMode; label: string }[] = [
  { value: "fast", label: "快速" },
  { value: "thorough", label: "精准" },
  { value: "edit", label: "编辑" },
];

/**
 * G3-3.1 · 快速 / 精准手动切换（HA-4-A）· G4-4.1 编辑全员可切（含 Member）。
 */
export function AgentModeSwitcher({
  value,
  onChange,
  disabled = false,
  className,
}: AgentModeSwitcherProps) {
  return (
    <div
      className={cn("agent-mode-switcher", className)}
      role="group"
      aria-label="大脑模式"
    >
      {MODES.map((mode) => (
        <button
          key={mode.value}
          type="button"
          className={cn(
            "agent-mode-btn",
            value === mode.value && "agent-mode-btn-active",
          )}
          aria-pressed={value === mode.value}
          disabled={disabled}
          data-testid={`agent-mode-${mode.value}`}
          onClick={() => onChange(mode.value)}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}
