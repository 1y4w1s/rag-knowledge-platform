/** G3 · 对话 Agent 模式（工程值 · UI 文案见 AgentModeSwitcher）· G4-4.1 扩展 edit · G5 扩展 document_write */
export type AgentMode = "fast" | "thorough" | "edit" | "document_write";

export const DEFAULT_AGENT_MODE: AgentMode = "fast";

export function agentModeLabel(mode: AgentMode): string {
  if (mode === "fast") return "快速";
  if (mode === "thorough") return "精准";
  if (mode === "edit") return "编辑";
  return "文档操作";
}
