/** G3 · Agent SSE tool_* / agent_budget 载荷（对齐 backend stream.py / research §3） */

import type { AgentMode } from "@/lib/agent-mode";

export interface AgentBudgetPayload {
  steps_used: number;
  max_steps: number;
  capped: boolean;
}

export interface AgentBudgetState {
  stepsUsed: number;
  maxSteps: number;
  capped: boolean;
}

export const DEFAULT_AGENT_MAX_STEPS = 5;

export function applyAgentBudget(
  payload: AgentBudgetPayload,
): AgentBudgetState {
  return {
    stepsUsed: payload.steps_used,
    maxSteps: payload.max_steps,
    capped: payload.capped,
  };
}

export function budgetChipLabel(
  mode: AgentMode,
  budget: AgentBudgetState | null,
): string {
  if (mode === "fast") {
    return "快速额度：充足";
  }
  const maxSteps = budget?.maxSteps ?? DEFAULT_AGENT_MAX_STEPS;
  if (budget?.capped) {
    return `精准额度：已达 ${maxSteps} 步上限`;
  }
  return "精准额度：充足";
}

export function budgetMeterPercent(budget: AgentBudgetState | null): number {
  const maxSteps = budget?.maxSteps ?? DEFAULT_AGENT_MAX_STEPS;
  const stepsUsed = budget?.stepsUsed ?? 0;
  if (maxSteps <= 0) return 0;
  return Math.min(100, Math.round((stepsUsed / maxSteps) * 100));
}

export interface ToolStartPayload {
  step: number;
  tool: string;
  args_summary: string;
}

export interface ToolResultPayload {
  step: number;
  tool: string;
  ok: boolean;
  summary: string;
  latency_ms: number;
  capped?: boolean;
}

export type ToolTimelineStepStatus = "running" | "done" | "error";

export interface ToolTimelineStep {
  step: number;
  tool: string;
  argsSummary?: string;
  summary?: string;
  ok?: boolean;
  latencyMs?: number;
  capped?: boolean;
  status: ToolTimelineStepStatus;
}

function sortByStep(steps: ToolTimelineStep[]): ToolTimelineStep[] {
  return [...steps].sort((a, b) => a.step - b.step);
}

export function applyToolStart(
  steps: ToolTimelineStep[],
  payload: ToolStartPayload,
): ToolTimelineStep[] {
  const existing = steps.find((row) => row.step === payload.step);
  if (existing) {
    return sortByStep(
      steps.map((row) =>
        row.step === payload.step
          ? {
              ...row,
              tool: payload.tool,
              argsSummary: payload.args_summary,
              status: "running" as const,
            }
          : row,
      ),
    );
  }
  return sortByStep([
    ...steps,
    {
      step: payload.step,
      tool: payload.tool,
      argsSummary: payload.args_summary,
      status: "running",
    },
  ]);
}

export function applyToolResult(
  steps: ToolTimelineStep[],
  payload: ToolResultPayload,
): ToolTimelineStep[] {
  const status: ToolTimelineStepStatus = payload.ok ? "done" : "error";
  const existing = steps.find((row) => row.step === payload.step);
  if (existing) {
    return sortByStep(
      steps.map((row) =>
        row.step === payload.step
          ? {
              ...row,
              tool: payload.tool,
              summary: payload.summary,
              ok: payload.ok,
              latencyMs: payload.latency_ms,
              capped: payload.capped,
              status,
            }
          : row,
      ),
    );
  }
  return sortByStep([
    ...steps,
    {
      step: payload.step,
      tool: payload.tool,
      summary: payload.summary,
      ok: payload.ok,
      latencyMs: payload.latency_ms,
      capped: payload.capped,
      status,
    },
  ]);
}

export function toolStepDetail(step: ToolTimelineStep): string {
  if (step.status === "running") {
    return step.argsSummary ?? "执行中…";
  }
  if (step.summary) {
    return step.latencyMs != null
      ? `${step.summary} · ${step.latencyMs}ms`
      : step.summary;
  }
  return step.argsSummary ?? "";
}
