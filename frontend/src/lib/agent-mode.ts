/** G3 · 对话 Agent 模式（工程值 · UI 文案见 AgentModeSwitcher）· G4-4.1 扩展 edit */
export type AgentMode = "fast" | "thorough" | "edit";

export const DEFAULT_AGENT_MODE: AgentMode = "fast";

export function agentModeLabel(mode: AgentMode): string {
  if (mode === "fast") return "快速";
  if (mode === "thorough") return "精准";
  return "编辑";
}
