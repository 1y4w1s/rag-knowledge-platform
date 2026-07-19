import {
  budgetChipLabel,
  budgetMeterPercent,
  type AgentBudgetState,
} from "@/lib/agent-stream";
import type { AgentMode } from "@/lib/agent-mode";
import { cn } from "@/lib/utils";

interface AgentBudgetChipProps {
  mode: AgentMode;
  budget: AgentBudgetState | null;
  className?: string;
}

/**
 * G3-3.3 · 精准模式步数 chip + meter（对齐 preview budget-chip · E-budget warn）。
 */
export function AgentBudgetChip({
  mode,
  budget,
  className,
}: AgentBudgetChipProps) {
  const capped = mode === "thorough" && Boolean(budget?.capped);
  const label = budgetChipLabel(mode, budget);
  const meterPct = budgetMeterPercent(budget);

  return (
    <div
      className={cn(
        "agent-budget-chip",
        capped && "agent-budget-chip-warn",
        className,
      )}
      data-testid="agent-budget-chip"
      data-capped={capped ? "true" : "false"}
    >
      <span className="agent-budget-chip-label">{label}</span>
      {mode === "thorough" ? (
        <div
          className="agent-budget-meter"
          aria-hidden="true"
          data-testid="agent-budget-meter"
        >
          <span style={{ width: `${meterPct}%` }} />
        </div>
      ) : null}
    </div>
  );
}
