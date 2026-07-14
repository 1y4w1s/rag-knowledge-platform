/** Options for discarding in-flight API responses after workspace switches (H8). */
export interface WorkspaceGenerationOptions {
  expectedGen: number;
  getCurrentGeneration: () => number;
  /** Explicit workspace from React context (avoids LS/context drift). */
  workspace?: import("@/lib/workspace-storage").WorkspaceId;
}

/** True when a newer `setWorkspace` / `resetToPersonal` bumped generation. */
export function isStaleWorkspaceGeneration(
  options: WorkspaceGenerationOptions | undefined,
): boolean {
  if (!options) return false;
  return options.getCurrentGeneration() !== options.expectedGen;
}
